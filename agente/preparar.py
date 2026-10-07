"""PREPARAR: cópia local do lago de produção, dbt no target `agente` e o contexto do agente.

Repete a sequência do pipeline sem a coleta: `coletor estado restaurar` (baixa o que mudou no
bucket e importa os históricos para o banco) e `dbt build`. O cache C2 valida dados, regras,
saída íntegra e ausência de tentativa pendente antes de reutilizar o banco.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import threading
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from agente.caderno import Caderno, Caso, ConsultaChave, mudou
from agente.config import ConfigAgente, preparo_c2_pendente, saida_tse_permitida
from agente.consulta import ErroConsulta, abrir, executar
from agente.diario import Diario
from coletor.esquemas import ARQUIVO_ESQUEMAS, carregar_esquemas, garantir_fontes
from coletor.hashes import json_canonico, sha256_arquivo
from coletor.tse.durabilidade import sincronizar_pasta
from coletor.tse.estado import validar_estado_tse
from coletor.tse.evidencias import inventario_saida
from coletor.tse.execucao import preparar_execucao_tse
from coletor.tse.modelos import SelecaoTse
from coletor.tse.selecao import digest_entradas, digest_selecao

Rodar = Callable[[list[str], Mapping[str, str], Path], int]
SCHEMAS = ("marts", "intermediate", "staging")
PASTAS_LAGO = ("raw", "meta", "estado")


class ErroPreparo(Exception):
    """O lago local não pôde ser preparado; a investigação não começa."""


@dataclass(frozen=True)
class Preparo:
    versao_dados: dict[str, str]
    dbt_rodou: bool
    revisar: list[Caso]  # casos confirmados ou descartados cujas consultas-chave mudaram


def _rodar_subprocesso(comando: list[str], env: Mapping[str, str], cwd: Path) -> int:
    return subprocess.run(comando, env=dict(env), cwd=cwd, check=False).returncode


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
    """Legado por caminho/tamanho, C2 por conteúdo selecionado, sem artefatos derivados."""
    resumo = hashlib.sha256()
    for pasta in PASTAS_LAGO:
        raiz = lago / pasta
        if not raiz.exists():
            continue
        for arquivo in sorted(p for p in raiz.rglob("*") if p.is_file()):
            relativo = arquivo.relative_to(lago).as_posix()
            if relativo.startswith(("raw/tse/", "meta/tse/", "estado/tse/")):
                continue
            resumo.update(
                f"{arquivo.relative_to(lago).as_posix()}|{arquivo.stat().st_size}\n".encode()
            )
    vigente = lago / "estado/tse/vigente.json"
    if vigente.exists():
        selecao = SelecaoTse(**json.loads(vigente.read_bytes()))
        resumo.update(digest_selecao(selecao).encode())
        resumo.update(digest_entradas(lago, selecao).encode())
    else:
        resumo.update(b"tse:bootstrap")
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


def gerar_contexto(
    config: ConfigAgente, segundos_contagem: float = 10, *, diretorios: list[Path] | None = None
) -> str:
    """contexto.md: tabelas de marts, intermediate e staging com colunas, tipos e linhas."""
    conexao = abrir(
        config.banco, diretorios if diretorios is not None else config.diretorios_permitidos()
    )
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


def revisar_caderno(
    config: ConfigAgente, caderno: Caderno, *, diretorios: list[Path] | None = None
) -> list[Caso]:
    """Casos confirmados ou descartados cujas consultas-chave mudaram desde o registro."""
    candidatos = [
        caso
        for caso in caderno.listar()
        if caso.situacao in ("confirmado", "descartado") and caso.consultas_chave
    ]
    if not candidatos:
        return []
    diario = Diario(config.lago / "revisao")
    conexao = abrir(
        config.banco, diretorios if diretorios is not None else config.diretorios_permitidos()
    )
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


# Escopo explícito C2: SQL/YAML TSE e macros próprias/compartilhadas usadas.
# Não promete detectar alterações de todo código/modelo legado.
REGRAS_C2 = (
    "dbt/macros/tse.sql",
    "dbt/macros/documentos.sql",
    "dbt/macros/conversoes.sql",
    "dbt/macros/generate_schema_name.sql",
    "dbt/tests/generic/sem_cpf_completo.sql",
    "dbt/tests/generic/sem_dados_pessoais.sql",
    # O monitor T16 depende dos hashes oficiais projetados neste staging compartilhado.
    "dbt/models/staging/stg_meta__coletas.sql",
    "dbt/models/staging/tse",
    "dbt/models/intermediate/tse",
    "dbt/models/marts/tse",
)


def _regras_c2(raiz: Path) -> str:
    resumo = hashlib.sha256()
    for relativo in REGRAS_C2:
        caminho = raiz / relativo
        arquivos = (
            sorted(p for p in caminho.rglob("*") if p.suffix in (".sql", ".yml", ".yaml"))
            if caminho.is_dir()
            else [caminho]
        )
        for arquivo in arquivos:
            resumo.update(arquivo.relative_to(raiz).as_posix().encode())
            resumo.update(arquivo.read_bytes() if arquivo.is_file() else b"ausente")
    return resumo.hexdigest()


def _cache_tse(config: ConfigAgente, anterior: dict, impressao: str, regras: str) -> bool:
    if (
        preparo_c2_pendente(config.lago)
        or anterior.get("impressao") != impressao
        or anterior.get("regras_c2") != regras
        or anterior.get("dbt") != "sucesso"
        or not config.banco.exists()
    ):
        return False
    try:
        tse = anterior["tse"]
        saida = saida_tse_permitida(config.lago, tse["execucao_id"], tse["saida"])
        preparacao = saida.parent / "preparacao.json"
        if preparacao.is_symlink() or preparacao.is_junction():
            return False
        dados = json.loads(preparacao.read_bytes())
        return (
            sha256_arquivo(preparacao) == tse["preparacao_sha256"]
            and dados["vars"] == tse["vars"]
            and dados["target"] == "agente"
            and inventario_saida(saida) == tse["inventario"]
        )
    except (KeyError, ValueError, OSError, TypeError):
        return False


def _gravar_marca(marca: Path, dados: dict) -> None:
    temporario = None
    try:
        with tempfile.NamedTemporaryFile(dir=marca.parent, delete=False) as arquivo:
            temporario = Path(arquivo.name)
            arquivo.write(json_canonico(dados).encode("utf8"))
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, marca)
        sincronizar_pasta(marca.parent)
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)


def preparar(
    config: ConfigAgente,
    base: Mapping[str, str],
    rodar: Rodar = _rodar_subprocesso,
    agora: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> Preparo:
    env = ambiente(config, base)
    restaurar = ["uv", "run", "coletor", "--target", "agente", "estado", "restaurar"]
    # da raiz do repositório: o coletor e o dbt usam caminhos relativos (fontes/, dbt/)
    if rodar(restaurar, env, config.raiz) != 0:
        raise ErroPreparo("coletor estado restaurar falhou (credenciais do GCS no .env?)")
    try:
        # A causalidade restaurada é obrigatória ANTES de qualquer cache/preparação.
        validar_estado_tse(config.lago)
        vigente = config.lago / "estado/tse/vigente.json"
        selecao = SelecaoTse(**json.loads(vigente.read_bytes())) if vigente.exists() else None
        esquemas = config.raiz / "dbt" / ARQUIVO_ESQUEMAS
        if esquemas.exists():
            garantir_fontes(config.lago, carregar_esquemas(config.raiz / "dbt"))
        impressao = impressao_lago(config.lago)
        regras = _regras_c2(config.raiz)
        marca = config.lago / "preparo.json"
        anterior = json.loads(marca.read_bytes()) if marca.exists() else {}
        dbt_rodou = False
        if not _cache_tse(config, anterior, impressao, regras):
            execucao_id = "agente-" + uuid.uuid4().hex
            # Persiste antes de alterar banco; não é estado sincronizado nem entrada do cache.
            _gravar_marca(
                config.lago / "preparo-c2-pendente.json",
                {
                    "execucao_id": execucao_id,
                    "impressao": impressao,
                    "regras_c2": regras,
                },
            )
            saida_tse_permitida(config.lago, execucao_id)
            execucao = preparar_execucao_tse(config.lago, execucao_id, "agente", selecao)
            (config.publico / "marts").mkdir(parents=True, exist_ok=True)
            dbt = [
                "uv",
                "run",
                "dbt",
                "build",
                "--project-dir",
                "dbt",
                "--profiles-dir",
                "dbt",
                "--target",
                "agente",
                "--exclude-resource-type",
                "unit_test",
                "--vars",
                json_canonico(execucao.vars_dbt),
                "--target-path",
                str(execucao.saida.parent / "dbt-target"),
            ]
            if rodar(dbt, env, config.raiz) != 0:
                raise ErroPreparo("dbt build falhou; investigação C2 bloqueada")
            if not config.banco.exists():
                raise ErroPreparo("dbt build não gerou o banco do agente")
            inventario = inventario_saida(execucao.saida)
            validar_estado_tse(config.lago)
            if impressao_lago(config.lago) != impressao or _regras_c2(config.raiz) != regras:
                raise ErroPreparo("entradas ou regras C2 mudaram durante dbt build")
            corrigir_particoes(config.banco)
            anterior = {
                "impressao": impressao,
                "regras_c2": regras,
                "dbt": "sucesso",
                "preparado_em": agora().isoformat(timespec="seconds"),
                "tse": {
                    "execucao_id": execucao_id,
                    "saida": str(execucao.saida),
                    "vars": execucao.vars_dbt,
                    "inventario": inventario,
                    "preparacao_sha256": sha256_arquivo(execucao.saida.parent / "preparacao.json"),
                },
            }
            dbt_rodou = True
        if dbt_rodou:
            diretorios = config.diretorios_dados() + [
                saida_tse_permitida(
                    config.lago, anterior["tse"]["execucao_id"], anterior["tse"]["saida"]
                )
            ]
        else:
            diretorios = config.diretorios_permitidos()
        config.investigacoes.mkdir(parents=True, exist_ok=True)
        (config.investigacoes / "contexto.md").write_text(
            gerar_contexto(config, diretorios=diretorios), encoding="utf-8"
        )
        revisar = revisar_caderno(config, Caderno(config.caderno), diretorios=diretorios)
        if dbt_rodou:
            _gravar_marca(marca, anterior)
            if json.loads(marca.read_bytes()) != anterior:
                raise ErroPreparo("marca C2 gravada com conteúdo divergente")
            # Falha de limpeza póscommit mantém bloqueio e erro; sem rollback fictício.
            (config.lago / "preparo-c2-pendente.json").unlink()
    except ErroPreparo:
        raise
    except Exception as erro:
        raise ErroPreparo(f"preparo C2 inválido: {erro}") from erro
    versao = {
        "lago": impressao,
        "dbt": anterior.get("dbt", "—"),
        "preparado_em": anterior.get("preparado_em", "—"),
    }
    return Preparo(versao_dados=versao, dbt_rodou=dbt_rodou, revisar=revisar)
