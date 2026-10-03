import json
from datetime import UTC, date, datetime

import pytest

from coletor.competencias import Competencia
from coletor.manifesto import RecursoCompleto
from coletor.meta import HistoricoColetas, RegistroColeta, RepositorioMeta, Sucesso
from tests.amostras import recurso

HOJE = date(2026, 10, 3)


def _instante(dia: date) -> datetime:
    return datetime(dia.year, dia.month, dia.day, 11, 0, tzinfo=UTC)


def _ceap() -> RecursoCompleto:
    return RecursoCompleto(
        "camara",
        recurso(
            id="ceap",
            url="https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip",
            publicacao="por_competencia",
            competencia={"tipo": "ano", "inicio": 2024},
            cadencia={"corrente": "diaria", "anteriores": "semanal"},
        ),
    )


def _sucesso(dia: date, competencia: date | None = None, colunas=None, sha="h") -> Sucesso:
    return Sucesso(_instante(dia), sha, competencia, colunas)


def test_colunas_de_referencia_usam_a_mesma_competencia_ou_a_anterior_mais_proxima():
    historico = HistoricoColetas(
        {
            ("camara.ceap", "2024"): _sucesso(HOJE, date(2024, 1, 1), [["A", "a"]]),
            ("camara.ceap", "2025"): _sucesso(HOJE, date(2025, 1, 1), [["B", "b"]]),
        }
    )
    assert historico.colunas_referencia("camara.ceap", Competencia.de_ano(2025)) == [["B", "b"]]
    assert historico.colunas_referencia("camara.ceap", Competencia.de_ano(2026)) == [["B", "b"]]
    assert historico.colunas_referencia("camara.ceap", Competencia.de_ano(2023)) is None


def _registro(status: str, colunas=None) -> RegistroColeta:
    registro = RegistroColeta.novo(
        "exec", _ceap(), Competencia.de_ano(2026), _instante(HOJE), "teste"
    )
    registro.sha256_conteudo = "novo"
    registro.colunas = colunas
    return registro.finalizar(status, _instante(HOJE))


def test_registrar_sem_alteracao_mantem_as_colunas_da_ultima_carga():
    historico = HistoricoColetas()
    historico.registrar(_registro("carregada", [["A", "a"]]))
    historico.registrar(_registro("sem_alteracao"))
    historico.registrar(_registro("falha"))
    assert historico.ultimo_sha("camara.ceap", "2026") == "novo"
    assert historico.colunas_referencia("camara.ceap", Competencia.de_ano(2026)) == [["A", "a"]]


def test_linha_de_coleta_serializa_json_e_datas():
    registro = _registro("carregada", [["A", "a"]])
    registro.parametros = {"x": 1}
    linha = registro.para_linha()
    assert json.loads(linha["parametros"]) == {"x": 1}
    assert json.loads(linha["colunas"]) == [["A", "a"]]
    assert linha["competencia_data"] == "2026-01-01"
    assert linha["iniciada_em"] == "2026-10-03T11:00:00+00:00"


def test_historico_e_montado_a_partir_da_consulta(warehouse, config):
    warehouse.resposta_consulta = [
        {
            "orgao": "camara",
            "recurso": "ceap",
            "competencia": "2025",
            "competencia_data": date(2025, 1, 1),
            "finalizada_em": _instante(HOJE),
            "sha256_conteudo": "abc",
            "colunas": '[["A", "a"]]',
        }
    ]
    historico = RepositorioMeta(warehouse, config).carregar_historico()
    assert historico.ultimo_sha("camara.ceap", "2025") == "abc"
    assert historico.ultima_data_sucesso("camara.ceap") == HOJE


def test_buscar_arquivo_original_exige_uuid(warehouse, config):
    with pytest.raises(ValueError):
        RepositorioMeta(warehouse, config).buscar_arquivo_original("1' OR '1'='1")
