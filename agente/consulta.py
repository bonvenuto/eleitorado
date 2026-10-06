"""Consultas do agente: uma instrução SELECT por vez, num DuckDB só de leitura e com acesso a
arquivos restrito ao lago. A trava é do próprio banco, não da instrução dada ao agente."""

from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pyarrow.parquet as pq

from agente.diario import Diario, RegistroConsulta


class ErroConsulta(Exception):
    """Consulta recusada ou com erro; a mensagem vai de volta para o agente."""


@dataclass(frozen=True)
class ResultadoConsulta:
    id: str
    linhas: int
    truncada: bool
    texto: str  # tabela em Markdown para o agente


def validar_sql(sql: str) -> str:
    """Devolve o texto da única instrução, que precisa ser SELECT (inclui WITH)."""
    try:
        instrucoes = duckdb.extract_statements(sql)
    except duckdb.Error as erro:
        raise ErroConsulta(f"SQL inválido: {erro}") from None
    if len(instrucoes) != 1:
        raise ErroConsulta(f"envie exatamente uma instrução (recebidas: {len(instrucoes)})")
    if instrucoes[0].type != duckdb.StatementType.SELECT:
        raise ErroConsulta(f"só SELECT é permitido (recebido: {instrucoes[0].type.name})")
    # sem o ; final e com quebras de linha: um comentário -- no fim não engole o resto
    return instrucoes[0].query.strip().rstrip(";").strip()


def abrir(banco: Path, diretorios: list[Path], memoria: str = "4GB") -> duckdb.DuckDBPyConnection:
    """Conexão só de leitura; arquivos só dos `diretorios` (as views do banco os leem)."""
    conexao = duckdb.connect(str(banco), read_only=True)
    lista = ", ".join("'" + d.resolve().as_posix().replace("'", "''") + "/'" for d in diretorios)
    conexao.execute(f"set memory_limit = '{memoria}'")
    conexao.execute(f"set allowed_directories = [{lista}]")
    conexao.execute("set enable_external_access = false")  # não pode ser religado na conexão
    return conexao


def _celula(valor: Any) -> str:
    texto = "" if valor is None else str(valor)
    texto = texto.replace("|", r"\|").replace("\n", " ")
    return texto if len(texto) <= 80 else texto[:77] + "..."


def _markdown(colunas: list[str], linhas: list[tuple]) -> str:
    cabecalho = "| " + " | ".join(colunas) + " |"
    separador = "|" + "---|" * len(colunas)
    corpo = ["| " + " | ".join(_celula(v) for v in linha) + " |" for linha in linhas]
    return "\n".join([cabecalho, separador, *corpo])


def executar(
    conexao: duckdb.DuckDBPyConnection,
    sql: str,
    diario: Diario,
    papel: str,
    tempo_maximo_s: float = 60,
    linhas_exibidas: int = 200,
    linhas_salvas: int = 100_000,
    caracteres_maximos: int = 12_000,
) -> ResultadoConsulta:
    texto_sql = validar_sql(sql)
    consulta_id = diario.proximo_id()
    temporizador = threading.Timer(tempo_maximo_s, conexao.interrupt)
    inicio = time.monotonic()
    temporizador.start()
    try:
        tabela = conexao.sql(
            f"select * from (\n{texto_sql}\n) as consulta limit {linhas_salvas + 1}"
        ).to_arrow_table()
    except duckdb.InterruptException:
        raise ErroConsulta(
            f"tempo esgotado ({tempo_maximo_s:.0f} s): simplifique a consulta"
        ) from None
    except duckdb.Error as erro:
        raise ErroConsulta(f"{type(erro).__name__}: {erro}") from None
    finally:
        temporizador.cancel()
    duracao = time.monotonic() - inicio
    truncada = tabela.num_rows > linhas_salvas
    if truncada:
        tabela = tabela.slice(0, linhas_salvas)
    destino = diario.caminho_resultado(consulta_id)
    destino.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(tabela, destino)
    diario.registrar(
        RegistroConsulta(
            id=consulta_id,
            sql=texto_sql,
            linhas=tabela.num_rows,
            truncada=truncada,
            colunas=tabela.column_names,
            sha256=hashlib.sha256(destino.read_bytes()).hexdigest(),
            executada_em=datetime.now(UTC).isoformat(timespec="seconds"),
            duracao_s=round(duracao, 3),
            papel=papel,
        )
    )
    exibidas = tabela.slice(0, linhas_exibidas)
    linhas = list(
        zip(*(exibidas.column(c).to_pylist() for c in exibidas.column_names), strict=True)
    )
    # o texto volta inteiro para o agente: resultados largos demais são cortados por linhas
    corpo = _markdown(tabela.column_names, linhas)
    cortado = False
    while len(corpo) > caracteres_maximos and len(linhas) > 1:
        linhas = linhas[: max(1, len(linhas) // 2)]
        corpo = _markdown(tabela.column_names, linhas)
        cortado = True
    total = f"mais de {linhas_salvas}" if truncada else str(tabela.num_rows)
    cabecalho = f"Consulta {consulta_id}: {total} linha(s)"
    if cortado:
        cabecalho += (
            f", mostrando as primeiras {len(linhas)} (limite de texto: agregue ou selecione "
            "menos colunas)"
        )
    elif tabela.num_rows > linhas_exibidas:
        cabecalho += f", mostrando as primeiras {linhas_exibidas}"
    return ResultadoConsulta(
        id=consulta_id,
        linhas=tabela.num_rows,
        truncada=truncada,
        texto=cabecalho + "\n\n" + corpo,
    )
