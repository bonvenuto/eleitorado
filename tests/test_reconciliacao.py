from datetime import date, datetime
from decimal import Decimal

from coletor.reconciliacao import COMPARACOES, reconciliar


def _consulta(respostas):
    """Responde pela posição da comparação (a mesma ordem nos dois lados)."""
    sqls = {c.bigquery: i for i, c in enumerate(COMPARACOES)}
    sqls.update({c.duckdb: i for i, c in enumerate(COMPARACOES)})
    return lambda sql: respostas.get(sqls[sql], [])


def test_lados_iguais_nao_divergem():
    respostas = {0: [("camara", 2025, 10, Decimal("100.50"))], 2: [("ceis:1",), ("ceis:2",)]}
    assert reconciliar(_consulta(respostas), _consulta(respostas)) == []


def test_normaliza_tipos_que_cada_banco_devolve():
    bigquery = {
        0: [("camara", 2025, 10, Decimal("100.5"))],
        4: [("s", "camara", date(2025, 1, 2), "x", 1.0)],
    }
    duckdb = {
        0: [("camara", "2025", 10, 100.50)],
        4: [("s", "camara", date(2025, 1, 2), "x", Decimal("1.00"))],
    }
    assert reconciliar(_consulta(bigquery), _consulta(duckdb)) == []
    assert (
        reconciliar(
            _consulta({1: [(datetime(2026, 1, 1, 10),)]}),
            _consulta({1: [("2026-01-01T10:00:00",)]}),
        )
        == []
    )


def test_diferenca_aparece_dos_dois_lados():
    bigquery = {2: [("ceis:1",), ("ceis:2",)]}
    duckdb = {2: [("ceis:1",), ("ceis:3",)]}
    [divergencia] = reconciliar(_consulta(bigquery), _consulta(duckdb))
    assert divergencia.nome == "sanções presentes"
    assert divergencia.so_no_bigquery == [("ceis:2",)]
    assert divergencia.so_no_duckdb == [("ceis:3",)]


def test_linha_repetida_conta():
    bigquery = {4: [("s", "camara", "d", "x", "1"), ("s", "camara", "d", "x", "1")]}
    duckdb = {4: [("s", "camara", "d", "x", "1")]}
    [divergencia] = reconciliar(_consulta(bigquery), _consulta(duckdb))
    assert divergencia.so_no_bigquery == [("s", "camara", "d", "x", "1")]
    assert divergencia.so_no_duckdb == []
