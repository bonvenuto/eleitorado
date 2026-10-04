from datetime import date

import httpx

from coletor.cli import main
from coletor.dbt import ResultadoDbt
from coletor.meta import RepositorioMeta
from tests.amostras import CNEP_CSV, PAGINA_CGU, RAIZ, zip_com

PAGINA = "https://portaldatransparencia.gov.br/download-de-dados/cnep"
ENV = {"ELEITORADO_PROJETO": "projeto-teste", "ELEITORADO_BUCKET": "bucket-teste"}


def _rodar(argumentos, deps, dbt) -> int:
    return main(
        ["--fontes", str(RAIZ / "fontes"), *argumentos],
        fabrica=lambda config: deps,
        env=ENV,
        dbt=dbt,
    )


def _mock_tudo_sem_alteracao(respx_mock):
    """Só o CNEP responde; o resto não está vencido porque o histórico já tem tudo."""
    respx_mock.get(PAGINA).mock(return_value=httpx.Response(200, text=PAGINA_CGU))
    respx_mock.get(f"{PAGINA}/20261002").mock(
        return_value=httpx.Response(
            200, content=zip_com({"20261002_CNEP.csv": CNEP_CSV.encode("cp1252")})
        )
    )


def test_pipeline_coleta_roda_dbt_e_registra_uma_execucao(respx_mock, deps, warehouse):
    _mock_tudo_sem_alteracao(respx_mock)
    chamadas = []

    def dbt(diretorio, target):
        chamadas.append((diretorio.name, target))
        return ResultadoDbt("sucesso", 0)

    codigo = _rodar(["pipeline", "--recursos", "cgu.cnep"], deps, dbt)
    assert codigo == 0
    assert chamadas == [("dbt", "prod")]
    [execucao] = warehouse.linhas["meta_dev.execucoes"]
    assert (execucao["status"], execucao["dbt_status"]) == ("sucesso", "sucesso")
    assert execucao["dbt_testes_com_erro"] == 0


def test_pipeline_com_dbt_falhando_termina_com_erro(respx_mock, deps, warehouse):
    _mock_tudo_sem_alteracao(respx_mock)
    codigo = _rodar(
        ["pipeline", "--recursos", "cgu.cnep"], deps, lambda d, t: ResultadoDbt("falha", 3)
    )
    assert codigo == 1
    [execucao] = warehouse.linhas["meta_dev.execucoes"]
    assert (execucao["status"], execucao["dbt_status"], execucao["dbt_testes_com_erro"]) == (
        "falha",
        "falha",
        3,
    )


def test_pipeline_roda_o_dbt_mesmo_com_falha_de_coleta(respx_mock, deps, warehouse):
    respx_mock.get(url__startswith=PAGINA).mock(return_value=httpx.Response(403))
    chamadas = []

    def dbt(diretorio, target):
        chamadas.append(target)
        return ResultadoDbt("sucesso", 0)

    assert _rodar(["pipeline", "--recursos", "cgu.cnep"], deps, dbt) == 1
    assert chamadas == ["prod"]
    [execucao] = warehouse.linhas["meta_dev.execucoes"]
    assert (execucao["status"], execucao["coletas_falha"], execucao["dbt_status"]) == (
        "falha",
        1,
        "sucesso",
    )


def test_pipeline_registra_a_execucao_mesmo_se_o_dbt_explodir(respx_mock, deps, warehouse):
    _mock_tudo_sem_alteracao(respx_mock)

    def dbt(diretorio, target):
        raise FileNotFoundError("dbt não instalado")

    assert _rodar(["pipeline", "--recursos", "cgu.cnep"], deps, dbt) == 1
    [execucao] = warehouse.linhas["meta_dev.execucoes"]
    assert (execucao["status"], execucao["dbt_status"]) == ("falha", "falha")


def test_vigia_aprova_quando_ha_execucao_agendada_com_sucesso_hoje(deps, warehouse):
    warehouse.resposta_consulta = [{"n": 1}]
    assert _rodar(["vigia"], deps, None) == 0
    assert warehouse.tabelas == set()  # não tenta criar tabelas: a conta do vigia só lê


def test_vigia_reprova_sem_execucao_agendada_com_sucesso(deps, warehouse, capsys):
    warehouse.resposta_consulta = [{"n": 0}]
    assert _rodar(["vigia"], deps, None) == 1
    assert "2026-10-03" in capsys.readouterr().err


def test_consulta_do_vigia_filtra_dia_origem_e_status(warehouse, config):
    consultas = []
    warehouse.consultar = lambda sql: consultas.append(sql) or [{"n": 2}]
    assert RepositorioMeta(warehouse, config).execucao_agendada_com_sucesso(date(2026, 10, 3))
    [sql] = consultas
    assert "origem = 'agendada'" in sql
    assert "status = 'sucesso'" in sql
    assert "DATE(iniciada_em, 'America/Sao_Paulo') = '2026-10-03'" in sql
