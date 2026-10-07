import pytest
from pydantic import ValidationError

from coletor.manifesto import Recurso, RegraCompetencia
from tests.amostras import recurso
from tests.amostras_tse import recurso_tse


def test_recurso_tse_preserva_familias_e_anos_explicitos():
    dados = recurso_tse("contas").model_dump()
    dados["familias"] = {"receitas": "receitas_{ano}_BRASIL.csv", "pagamentos": "pagamentos_*.csv"}
    dados["competencia"].pop("inicio")
    validado = Recurso.model_validate(dados)
    assert validado.competencia.anos == [2018, 2020, 2022, 2024]
    assert validado.familias == {
        "receitas": "receitas_{ano}_BRASIL.csv",
        "pagamentos": "pagamentos_*.csv",
    }


@pytest.mark.parametrize("anos", [[], [2018, 2018]])
def test_anos_explicitos_nao_podem_ser_vazios_ou_repetidos(anos):
    with pytest.raises(ValidationError, match="anos"):
        RegraCompetencia(tipo="ano", anos=anos)


@pytest.mark.parametrize("tipo", ["mes", "dia", "data_arquivo", "data_coleta"])
def test_anos_explicitos_so_valem_para_tipo_ano(tipo):
    with pytest.raises(ValidationError, match="anos"):
        RegraCompetencia(tipo=tipo, anos=[2018])


def test_familias_so_valem_para_tse_zip():
    with pytest.raises(ValidationError, match="familias"):
        recurso(familias={"candidaturas": "consulta_*.csv"})


@pytest.mark.parametrize("familias", [None, {}])
def test_tse_zip_exige_familias(familias):
    dados = recurso_tse("contas").model_dump() | {"familias": familias}
    with pytest.raises(ValidationError, match="familias"):
        Recurso.model_validate(dados)


@pytest.mark.parametrize("formato", [{"tipo": "json", "compressao": "zip"}, {"tipo": "csv"}])
def test_tse_zip_exige_csv_zip(formato):
    dados = recurso_tse("contas").model_dump() | {"formato": formato}
    with pytest.raises(ValidationError, match="csv.*zip"):
        Recurso.model_validate(dados)
