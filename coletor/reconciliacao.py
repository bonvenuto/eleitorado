"""Reconciliação temporária (paralelo da migração): marts do DuckDB contra os do BigQuery.

Sai na virada (Plano 5), junto com a dependência opcional `google-cloud-bigquery`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

Consulta = Callable[[str], list[tuple[Any, ...]]]


@dataclass(frozen=True)
class Comparacao:
    nome: str
    bigquery: str  # sobre o dataset `marts`
    duckdb: str  # sobre views com o nome de cada mart


FCT = "fct_despesa_cota_parlamentar"

COMPARACOES = [
    Comparacao(
        "cota por casa e ano",
        f"select casa, ano, count(*), round(sum(valor_reembolsado), 2) "
        f"from marts.{FCT} group by 1, 2",
        f"select casa, ano, count(*), round(sum(valor_reembolsado), 2) from {FCT} group by 1, 2",
    ),
    Comparacao(
        "cota por tipo de documento",
        f"select casa, fornecedor_tipo_documento, count(*) from marts.{FCT} group by 1, 2",
        f"select casa, fornecedor_tipo_documento, count(*) from {FCT} group by 1, 2",
    ),
    Comparacao(
        "sanções presentes",
        "select sancao_id from marts.fct_sancao",
        "select sancao_id from fct_sancao",
    ),
    Comparacao(
        "eventos do histórico de sanções",
        "select evento, count(*) from marts.fct_sancao_historico group by 1",
        "select evento, count(*) from fct_sancao_historico group by 1",
    ),
    Comparacao(
        "alertas de fornecedor sancionado",
        "select sancao_id, casa, data_emissao, fornecedor_documento, valor_reembolsado "
        "from marts.alerta_cota_fornecedor_sancionado",
        "select sancao_id, casa, data_emissao, fornecedor_documento, valor_reembolsado "
        "from alerta_cota_fornecedor_sancionado",
    ),
    *[
        Comparacao(
            f"linhas de {mart}",
            f"select count(*) from marts.{mart}",
            f"select count(*) from {mart}",
        )
        for mart in ("alerta_cota_documento_invalido", "dim_uf", "dim_municipio", "dim_parlamentar")
    ],
]


@dataclass(frozen=True)
class Divergencia:
    nome: str
    so_no_bigquery: list[tuple[str, ...]]
    so_no_duckdb: list[tuple[str, ...]]


def _normalizar(valor: Any) -> str:
    if valor is None:
        return "∅"
    if isinstance(valor, Decimal | float):
        return str(Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    if isinstance(valor, datetime | date):
        return valor.isoformat()
    return str(valor)


def _multiconjunto(linhas: Iterable[tuple[Any, ...]]) -> list[tuple[str, ...]]:
    return sorted(tuple(_normalizar(v) for v in linha) for linha in linhas)


def _diferenca(a: list[tuple[str, ...]], b: list[tuple[str, ...]]) -> list[tuple[str, ...]]:
    restante = list(b)
    sobra = []
    for linha in a:
        if linha in restante:
            restante.remove(linha)
        else:
            sobra.append(linha)
    return sobra


def reconciliar(consultar_bigquery: Consulta, consultar_duckdb: Consulta) -> list[Divergencia]:
    divergencias = []
    for comparacao in COMPARACOES:
        bq = _multiconjunto(consultar_bigquery(comparacao.bigquery))
        dk = _multiconjunto(consultar_duckdb(comparacao.duckdb))
        if bq != dk:
            divergencias.append(
                Divergencia(comparacao.nome, _diferenca(bq, dk), _diferenca(dk, bq))
            )
    return divergencias


def consulta_duckdb(publico: Path) -> Consulta:
    """Views sobre os Parquets publicados, com o nome de cada mart."""
    import duckdb

    conexao = duckdb.connect()
    marts = publico / "marts"
    for arquivo in sorted(marts.glob("*.parquet")):
        conexao.execute(
            f"create view {arquivo.stem} as select * from read_parquet('{arquivo.as_posix()}')"
        )
    conexao.execute(
        f"create view {FCT} as select * from read_parquet("
        f"'{(marts / FCT).as_posix()}/**/*.parquet', hive_partitioning = true)"
    )
    return lambda sql: conexao.execute(sql).fetchall()


def consulta_bigquery(projeto: str, credenciais: Any = None) -> Consulta:
    from google.cloud import bigquery

    cliente = bigquery.Client(
        project=projeto, location="southamerica-east1", credentials=credenciais
    )
    return lambda sql: [tuple(linha.values()) for linha in cliente.query(sql).result()]
