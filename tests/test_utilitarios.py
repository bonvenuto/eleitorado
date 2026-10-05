from datetime import date

import pytest

from coletor.competencias import Competencia, data_brasilia, legislatura_atual, legislaturas
from coletor.hashes import sha256_registros
from coletor.nomes import normalizar_cabecalho, normalizar_nome_coluna
from tests.amostras import AGORA


@pytest.mark.parametrize(
    ("dia", "esperada"),
    [
        (date(2026, 10, 3), 57),
        (date(2027, 1, 31), 57),
        (date(2027, 2, 1), 58),
        (date(2007, 2, 1), 53),
        (date(2007, 1, 31), 52),
    ],
)
def test_legislatura_atual_muda_em_1o_de_fevereiro(dia, esperada):
    assert legislatura_atual(dia) == esperada


def test_legislaturas_da_53a_ate_a_atual():
    assert legislaturas(53, date(2026, 10, 3)) == [53, 54, 55, 56, 57]


def test_competencia_a_partir_do_rotulo():
    assert Competencia.de_rotulo("2025") == Competencia("2025", date(2025, 1, 1))
    assert Competencia.de_rotulo("2026-10-02") == Competencia("2026-10-02", date(2026, 10, 2))


def test_data_em_brasilia():
    assert data_brasilia(AGORA) == date(2026, 10, 3)


@pytest.mark.parametrize(
    ("original", "normalizado"),
    [
        ("ABRAGÊNCIA DA SANÇÃO", "abragencia_da_sancao"),
        ("RAZÃO SOCIAL - CADASTRO RECEITA", "razao_social_cadastro_receita"),
        ("txNomeParlamentar", "txnomeparlamentar"),
        ("Nº", "no"),
        ("1º ano", "c_1o_ano"),
        ("", "coluna"),
    ],
)
def test_normalizar_nome_coluna(original, normalizado):
    assert normalizar_nome_coluna(original) == normalizado


def test_normalizar_cabecalho_desfaz_colisoes():
    nomes, pares = normalizar_cabecalho(["Valor", "VALOR", "valor_2"])
    assert nomes == ["valor", "valor_2", "valor_2_2"]
    assert pares[1] == ["VALOR", "valor_2"]


def test_hash_de_registros_ignora_ordem_de_registros_e_de_chaves():
    assert sha256_registros([{"a": 1, "b": 2}, {"c": 3}]) == sha256_registros(
        [{"c": 3}, {"b": 2, "a": 1}]
    )
    assert sha256_registros([{"a": 1}]) != sha256_registros([{"a": 2}])


def test_competencia_mensal():
    from coletor.competencias import Competencia, meses

    assert Competencia.de_mes(2024, 4) == Competencia("2024-04", date(2024, 4, 1))
    assert Competencia.de_rotulo("2024-04") == Competencia.de_mes(2024, 4)
    assert meses(date(2023, 11, 1), date(2024, 2, 1)) == [
        date(2023, 11, 1),
        date(2023, 12, 1),
        date(2024, 1, 1),
        date(2024, 2, 1),
    ]
