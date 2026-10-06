"""PREPARAR: cópia local do lago de produção, dbt no target `agente` e o contexto do agente.

Repete a sequência do pipeline sem a coleta: `coletor estado restaurar` (baixa o que mudou no
bucket e importa os históricos para o banco) e `dbt build`. O dbt só roda quando o lago mudou.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from agente.caderno import Caderno, Caso, ConsultaChave, mudou
from agente.config import ConfigAgente
from agente.consulta import ErroConsulta, abrir, executar
from agente.diario import Diario

Rodar = Callable[[list[str], Mapping[str, str]], int]
SCHEMAS = ("marts", "intermediate", "staging")
PASTAS_LAGO = ("raw", "meta", "estado")


class ErroPreparo(Exception):
    """O lago local não pôde ser preparado; a investigação não começa."""


@dataclass(frozen=True)
class Preparo:
    versao_dados: dict[str, str]
    dbt_rodou: bool
    revisar: list[Caso]  # casos confirmados ou descartados cujas consultas-chave mudaram


def _rodar_subprocesso(comando: list[str], env: Mapping[str, str]) -> int:
    return subprocess.run(comando, env=dict(env), check=False).returncode


def ler_env(arquivo: Path) -> dict[str, str]:
    """Variáveis de um arquivo .env (KEY=VALOR por linha; # comenta)."""
    variaveis: dict[str, str] = {}
    if not arquivo.exists():
        return variaveis
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        variaveis[chave.strip()] = valor.strip().strip('"').strip("'")
    return variaveis


def ambiente(config: ConfigAgente, base: Mapping[str, str]) -> dict[str, str]:
    """Ambiente do coletor e do dbt: credenciais do .env, mas lendo o lago de produção."""
    env = dict(base) | ler_env(config.raiz / ".env")
    env |= {
        "ELEITORADO_AMBIENTE": "prod",
        "ELEITORADO_PREFIXO": config.prefixo_gcs,
        "ELEITORADO_LAGO": str(config.lago),
        "ELEITORADO_PUBLICO": str(config.publico),
    }
    return env


def impressao_lago(lago: Path) -> str:
    """Impressão digital do lago (caminho e tamanho de cada arquivo): muda quando algo baixa."""
    resumo = hashlib.sha256()
    for pasta in PASTAS_LAGO:
        raiz = lago / pasta
        if not raiz.exists():
            continue
        for arquivo in sorted(p for p in raiz.rglob("*") if p.is_file()):
            resumo.update(
                f"{arquivo.relative_to(lago).as_posix()}|{arquivo.stat().st_size}\n".encode()
            )
    return resumo.hexdigest()[:16]


def corrigir_particoes(banco: Path) -> list[str]:
    """As views dos marts particionados (`.../coluna=valor/...`) que o dbt-duckdb cria leem os
    arquivos sem `hive_partitioning`, e as colunas de partição (casa, ano...) somem. Recria essas
    views com a partição; devolve as corrigidas."""
    import re

    conexao = duckdb.connect(str(banco))
    corrigidas = []
    try:
        for nome, sql in conexao.sql(
            "select view_name, sql from duckdb_views() where schema_name = 'marts'"
        ).fetchall():
            caminho = re.search(r"read_parquet\('([^']+)'", sql)
            if caminho and "*/*" in caminho.group(1):
                destino = caminho.group(1).replace("'", "''")
                conexao.execute(
                    f"create or replace view marts.{nome} as select * from "
                    f"read_parquet('{destino}', hive_partitioning = true)"
                )
                corrigidas.append(nome)
    finally:
        conexao.close()
    return corrigidas


def _contar(conexao: duckdb.DuckDBPyConnection, tabela: str, segundos: float) -> str:
    temporizador = threading.Timer(segundos, conexao.interrupt)
    temporizador.start()
    try:
        return f"{conexao.sql(f'select count(*) from {tabela}').fetchone()[0]:,}".replace(",", ".")
    except duckdb.Error:
        return "—"
    finally:
        temporizador.cancel()


def gerar_contexto(config: ConfigAgente, segundos_contagem: float = 10) -> str:
    """contexto.md: tabelas de marts, intermediate e staging com colunas, tipos e linhas."""
    conexao = abrir(config.banco, config.diretorios_permitidos())
    try:
        colunas: dict[tuple[str, str], list[str]] = {}
        for schema, tabela, coluna, tipo in conexao.sql(
            "select table_schema, table_name, column_name, data_type "
            "from information_schema.columns "
            f"where table_schema in {SCHEMAS} order by table_schema, table_name, ordinal_position"
        ).fetchall():
            colunas.setdefault((schema, tabela), []).append(f"{coluna} {tipo}")
        partes = [
            "# Contexto dos dados",
            "",
            "Banco DuckDB só de leitura. Consulte com `schema.tabela`. Camadas:",
            "",
            "- `marts`: dados publicados (CPF mascarado), prontos para análise.",
            "- `intermediate`: regras de negócio com o documento COMPLETO (CPF inclusive), "
            "históricos e todos os participantes de licitação.",
            "- `staging`: o raw tipado, uma view por recurso (inclui todas as esferas do PNCP).",
            "",
            "Dicionário completo dos marts: docs/modelos-de-dados.md (no repositório).",
        ]
        for schema in SCHEMAS:
            partes += ["", f"## {schema}", ""]
            for (esquema, tabela), lista in colunas.items():
                if esquema != schema:
                    continue
                linhas = _contar(conexao, f"{esquema}.{tabela}", segundos_contagem)
                partes.append(f"- `{esquema}.{tabela}` ({linhas} linhas): " + ", ".join(lista))
        if ("marts", "monitor_fontes") in colunas:
            partes += ["", "## Situação das fontes (marts.monitor_fontes)", ""]
            for recurso, sucesso, status, atraso in conexao.sql(
                "select recurso_id, ultimo_sucesso, status_ultima_coleta, atraso_horas "
                "from marts.monitor_fontes order by recurso_id"
            ).fetchall():
                partes.append(f"- `{recurso}`: último sucesso {sucesso} ({status}, {atraso} h)")
        return "\n".join(partes) + "\n"
    finally:
        conexao.close()


def _somar(tabela) -> float | None:
    import pyarrow as pa
    import pyarrow.compute as pc

    numericas = [
        c
        for c, tipo in zip(tabela.column_names, tabela.schema.types, strict=True)
        if pa.types.is_integer(tipo) or pa.types.is_floating(tipo) or pa.types.is_decimal(tipo)
    ]
    if not numericas:
        return None
    # float em cada coluna: as decimais (valores dos marts) não somam com float
    return sum(float(pc.sum(tabela.column(c)).as_py() or 0) for c in numericas)


def medir(conexao: duckdb.DuckDBPyConnection, sql: str, diario: Diario) -> ConsultaChave:
    """Executa uma consulta-chave e resume o resultado (linhas e soma das colunas numéricas)."""
    import pyarrow.parquet as pq

    resultado = executar(conexao, sql, diario, "controlador", linhas_exibidas=0)
    tabela = pq.read_table(diario.caminho_resultado(resultado.id))
    return ConsultaChave(sql=sql, linhas=tabela.num_rows, soma=_somar(tabela))


def revisar_caderno(config: ConfigAgente, caderno: Caderno) -> list[Caso]:
    """Casos confirmados ou descartados cujas consultas-chave mudaram desde o registro."""
    candidatos = [
        caso
        for caso in caderno.listar()
        if caso.situacao in ("confirmado", "descartado") and caso.consultas_chave
    ]
    if not candidatos:
        return []
    diario = Diario(config.lago / "revisao")
    conexao = abrir(config.banco, config.diretorios_permitidos())
    revisar = []
    try:
        for caso in candidatos:
            for anterior in caso.consultas_chave:
                try:
                    atual = medir(conexao, anterior.sql, diario)
                except ErroConsulta:
                    revisar.append(caso)  # a consulta deixou de funcionar: vale olhar de novo
                    break
                if mudou(anterior, atual.linhas, atual.soma):
                    revisar.append(caso)
                    break
    finally:
        conexao.close()
    return revisar


def preparar(
    config: ConfigAgente,
    base: Mapping[str, str],
    rodar: Rodar = _rodar_subprocesso,
    agora: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> Preparo:
    env = ambiente(config, base)
    restaurar = ["uv", "run", "coletor", "--target", "agente", "estado", "restaurar"]
    if rodar(restaurar, env) != 0:
        raise ErroPreparo("coletor estado restaurar falhou (credenciais do GCS no .env?)")
    impressao = impressao_lago(config.lago)
    marca = config.lago / "preparo.json"
    anterior = json.loads(marca.read_text(encoding="utf-8")) if marca.exists() else {}
    dbt_rodou = False
    if anterior.get("impressao") != impressao or not config.banco.exists():
        (config.publico / "marts").mkdir(parents=True, exist_ok=True)
        dbt = [
            "uv", "run", "dbt", "build", "--project-dir", "dbt", "--profiles-dir", "dbt",
            "--target", "agente", "--exclude-resource-type", "unit_test",
        ]  # fmt: skip
        codigo = rodar(dbt, env)
        if not config.banco.exists():
            raise ErroPreparo("dbt build não gerou o banco do agente")
        corrigir_particoes(config.banco)
        dbt_rodou = True
        anterior = {
            "impressao": impressao,
            "dbt": "sucesso" if codigo == 0 else "com falhas",
            "preparado_em": agora().isoformat(timespec="seconds"),
        }
        marca.write_text(json.dumps(anterior), encoding="utf-8")
    config.investigacoes.mkdir(parents=True, exist_ok=True)
    (config.investigacoes / "contexto.md").write_text(gerar_contexto(config), encoding="utf-8")
    revisar = revisar_caderno(config, Caderno(config.caderno))
    versao = {
        "lago": impressao,
        "dbt": anterior.get("dbt", "—"),
        "preparado_em": anterior.get("preparado_em", "—"),
    }
    return Preparo(versao_dados=versao, dbt_rodou=dbt_rodou, revisar=revisar)
