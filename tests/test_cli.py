import httpx
import pytest

from coletor.cli import main
from tests.amostras import CEAP_CSV, CNEP_CSV, PAGINA_CGU, RAIZ, zip_com

PAGINA = "https://portaldatransparencia.gov.br/download-de-dados/cnep"
ENV = {"ELEITORADO_PROJETO": "projeto-teste", "ELEITORADO_BUCKET": "bucket-teste"}


def _rodar(argumentos: list[str], deps) -> int:
    return main(
        ["--fontes", str(RAIZ / "fontes"), *argumentos], fabrica=lambda config: deps, env=ENV
    )


def test_executar_coleta_o_recurso_pedido_e_registra_tudo(respx_mock, deps, warehouse):
    respx_mock.get(PAGINA).mock(return_value=httpx.Response(200, text=PAGINA_CGU))
    respx_mock.get(f"{PAGINA}/20261002").mock(
        return_value=httpx.Response(
            200, content=zip_com({"20261002_CNEP.csv": CNEP_CSV.encode("cp1252")})
        )
    )
    assert _rodar(["executar", "--recursos", "cgu.cnep"], deps) == 0
    [coleta] = warehouse.linhas["meta/coletas"]
    [execucao] = warehouse.linhas["meta/execucoes"]
    assert (coleta["recurso"], coleta["status"], coleta["linhas"]) == ("cnep", "carregada", 2)
    assert (execucao["status"], execucao["coletas_carregadas"], execucao["origem"]) == (
        "sucesso",
        1,
        "manual",
    )
    assert len(warehouse.linhas["meta/fontes"]) == 14
    assert "meta/coletas" in warehouse.tabelas


def test_executar_com_falha_sai_com_codigo_1(respx_mock, deps, warehouse):
    respx_mock.get(url__startswith=PAGINA).mock(return_value=httpx.Response(403))
    assert _rodar(["executar", "--recursos", "cgu.cnep"], deps) == 1
    [execucao] = warehouse.linhas["meta/execucoes"]
    assert (execucao["status"], execucao["coletas_falha"]) == ("falha", 1)


def test_coletar_intervalo_de_anos(respx_mock, deps, warehouse):
    for ano in (2025, 2026):
        respx_mock.get(f"https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip").mock(
            return_value=httpx.Response(200, content=zip_com({f"Ano-{ano}.csv": CEAP_CSV.encode()}))
        )
    assert _rodar(["coletar", "camara.ceap", "--de", "2025"], deps) == 0
    competencias = [linha["competencia"] for linha in warehouse.linhas["meta/coletas"]]
    assert competencias == ["2025", "2026"]


def test_coletar_snapshot_com_competencia_e_erro_de_uso(deps, capsys):
    assert _rodar(["coletar", "cgu.cnep", "--competencia", "2025"], deps) == 2
    assert "snapshot" in capsys.readouterr().err


def test_sem_configuracao_sai_com_codigo_2(capsys):
    codigo = main(["--fontes", str(RAIZ / "fontes"), "fontes"], fabrica=None, env={})
    assert codigo == 2
    assert "ELEITORADO_PROJETO" in capsys.readouterr().err


@pytest.mark.parametrize(
    "argumentos", [["coletar", "camara.ceap"], ["coletar", "camara.ceap", "--ate", "2025"]]
)
def test_coletar_por_competencia_sem_anos_e_erro_de_uso(deps, argumentos):
    assert _rodar(argumentos, deps) == 2


COLETA_ID = "6f1c2a3b-0000-4000-8000-000000000001"


def test_falha_ao_gravar_meta_nao_interrompe_as_demais_coletas(respx_mock, deps, warehouse):
    for ano in (2025, 2026):
        respx_mock.get(f"https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip").mock(
            return_value=httpx.Response(200, content=zip_com({f"Ano-{ano}.csv": CEAP_CSV.encode()}))
        )
    warehouse.falhas_ao_anexar["meta/coletas"] = 2  # a gravação da 1ª coleta falha duas vezes
    assert _rodar(["coletar", "camara.ceap", "--de", "2025"], deps) == 1
    assert [linha["competencia"] for linha in warehouse.linhas["meta/coletas"]] == ["2026"]
    [execucao] = warehouse.linhas["meta/execucoes"]
    assert (execucao["status"], execucao["coletas_carregadas"], execucao["coletas_falha"]) == (
        "falha",
        1,
        1,
    )
