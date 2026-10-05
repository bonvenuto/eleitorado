import pytest
from pydantic import ValidationError

from coletor.manifesto import ErroManifesto, carregar_manifesto
from tests.amostras import RAIZ, recurso


def test_manifesto_do_repositorio_tem_os_sete_recursos_da_onda_a():
    manifesto = carregar_manifesto(RAIZ / "fontes")
    assert sorted(manifesto.recursos) == [
        "camara.ceap",
        "camara.deputados",
        "cgu.ceis",
        "cgu.cnep",
        "cgu.contratos",
        "cgu.emendas",
        "cgu.emendas_convenios",
        "cgu.emendas_documentos",
        "cgu.emendas_favorecidos",
        "cgu.licitacoes",
        "cgu.licitacoes_participantes",
        "ibge.municipios",
        "senado.ceaps",
        "senado.senadores",
    ]


def test_por_competencia_exige_ano_e_cadencia_anteriores():
    with pytest.raises(ValidationError, match="cadencia.anteriores"):
        recurso(
            publicacao="por_competencia",
            competencia={"tipo": "ano", "inicio": 2008},
            cadencia={"corrente": "diaria"},
        )


def test_data_arquivo_exige_pagina():
    with pytest.raises(ValidationError, match="pagina"):
        recurso(competencia={"tipo": "data_arquivo"})


def test_campo_desconhecido_no_manifesto_e_rejeitado(tmp_path):
    (tmp_path / "x.yaml").write_text(
        "orgao: x\nnome: X\nportal: https://x\nrecursos: []\ncampo_inventado: 1\n", encoding="utf-8"
    )
    with pytest.raises(ErroManifesto, match="x.yaml"):
        carregar_manifesto(tmp_path)


def test_recurso_duplicado_entre_arquivos_e_rejeitado(tmp_path):
    texto = (RAIZ / "fontes" / "ibge.yaml").read_text(encoding="utf-8")
    (tmp_path / "a.yaml").write_text(texto, encoding="utf-8")
    (tmp_path / "b.yaml").write_text(texto, encoding="utf-8")
    with pytest.raises(ErroManifesto, match="duplicado"):
        carregar_manifesto(tmp_path)


def test_recurso_inexistente():
    manifesto = carregar_manifesto(RAIZ / "fontes")
    with pytest.raises(ErroManifesto, match="desconhecido"):
        manifesto.obter("cgu.nao_existe")


def test_competencia_mensal_valida_e_fim_so_para_mes():
    from coletor.manifesto import RegraCompetencia

    assert RegraCompetencia(tipo="mes", inicio=2013, fim="2024-04").fim == "2024-04"
    with pytest.raises(ValueError):
        RegraCompetencia(tipo="mes", inicio=2013, fim="2024-4")
    with pytest.raises(ValueError):
        RegraCompetencia(tipo="ano", inicio=2013, fim="2024-04")


def test_competencia_dia_e_cadencia_anual():
    from coletor.manifesto import RegraCadencia, RegraCompetencia

    assert RegraCompetencia(tipo="dia", inicio=2021).tipo == "dia"
    assert RegraCadencia(corrente="semanal", anteriores="anual").anteriores == "anual"
