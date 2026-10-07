import httpx

from coletor.cli import main
from coletor.dbt import ResultadoDbt
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

    def dbt(diretorio, target, publico, argumentos=()):
        chamadas.append((diretorio.name, target, publico.as_posix()))
        return ResultadoDbt("sucesso", 0)

    codigo = _rodar(["pipeline", "--recursos", "cgu.cnep"], deps, dbt)
    assert codigo == 0
    assert chamadas == [("dbt", "prod", "dados/publico")]
    [execucao] = warehouse.linhas["meta/execucoes"]
    assert (execucao["status"], execucao["dbt_status"]) == ("sucesso", "sucesso")
    assert execucao["dbt_testes_com_erro"] == 0


def test_pipeline_deixa_os_modelos_do_site_para_o_coletor_site(respx_mock, deps):
    # uma falha nos modelos do site não pode impedir a publicação dos marts
    _mock_tudo_sem_alteracao(respx_mock)
    argumentos_vistos = []

    def dbt(diretorio, target, publico, argumentos=()):
        argumentos_vistos.append(list(argumentos))
        return ResultadoDbt("sucesso", 0)

    _rodar(["pipeline", "--recursos", "cgu.cnep"], deps, dbt)
    assert argumentos_vistos == [["--exclude", "path:models/site", "site_alerta_tipos"]]


def test_pipeline_com_dbt_falhando_termina_com_erro(respx_mock, deps, warehouse):
    _mock_tudo_sem_alteracao(respx_mock)
    codigo = _rodar(
        ["pipeline", "--recursos", "cgu.cnep"], deps, lambda d, t, p, a=(): ResultadoDbt("falha", 3)
    )
    assert codigo == 1
    [execucao] = warehouse.linhas["meta/execucoes"]
    assert (execucao["status"], execucao["dbt_status"], execucao["dbt_testes_com_erro"]) == (
        "falha",
        "falha",
        3,
    )


def test_pipeline_roda_o_dbt_mesmo_com_falha_de_coleta(respx_mock, deps, warehouse):
    respx_mock.get(url__startswith=PAGINA).mock(return_value=httpx.Response(403))
    chamadas = []

    def dbt(diretorio, target, publico, argumentos=()):
        chamadas.append(target)
        return ResultadoDbt("sucesso", 0)

    assert (
        _rodar(["pipeline", "--recursos", "cgu.cnep"], deps, dbt) == 3
    )  # só coletas falharam: publicável
    assert chamadas == ["prod"]
    [execucao] = warehouse.linhas["meta/execucoes"]
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
    [execucao] = warehouse.linhas["meta/execucoes"]
    assert (execucao["status"], execucao["dbt_status"]) == ("falha", "falha")


def test_pipeline_com_falha_de_coleta_e_de_dbt_sai_com_1(respx_mock, deps):
    respx_mock.get(url__startswith=PAGINA).mock(return_value=httpx.Response(403))

    def dbt(diretorio, target, publico, argumentos=()):
        return ResultadoDbt("falha", 2)

    assert _rodar(["pipeline", "--recursos", "cgu.cnep"], deps, dbt) == 1


def test_pipeline_legado_prepara_bootstrap_privado(deps, tmp_path, monkeypatch):
    import json
    from dataclasses import replace

    from coletor import cli
    from coletor.execucao import ResumoColetas

    deps.config = replace(deps.config, lago=tmp_path / "lago", publico=tmp_path / "publico")
    monkeypatch.setattr(cli, "rodar", lambda *a: ResumoColetas())
    chamadas = []

    def dbt(diretorio, target, publico, argumentos=()):
        chamadas.append(json.loads(argumentos[argumentos.index("--vars") + 1]))
        return ResultadoDbt("sucesso", 0)

    assert _rodar(["pipeline", "--recursos", "ibge.municipios"], deps, dbt) == 0
    [variaveis] = chamadas
    assert set(variaveis["tse_fontes"]) == {
        "candidaturas",
        "bens",
        "receitas",
        "contratadas",
        "pagamentos",
        "doador_originario",
    }
    assert variaveis["tse_proveniencia"]
    assert variaveis["tse_saida"].startswith(
        (deps.config.lago / "estado/tse/publicacoes/preparadas").as_posix()
    )
    assert not (deps.config.lago / "estado/tse/vigente.json").exists()


def test_pipeline_marcador_sem_vigente_falha(deps, tmp_path, monkeypatch):
    from dataclasses import replace

    from coletor import cli
    from coletor.execucao import ResumoColetas

    deps.config = replace(deps.config, lago=tmp_path / "lago")
    estado = deps.config.lago / "estado/tse"
    estado.mkdir(parents=True)
    (estado / "inicializado.json").write_text("{}")
    monkeypatch.setattr(cli, "rodar", lambda *a: ResumoColetas())

    def dbt(*a, **kw):
        raise AssertionError("nao deve executar dbt")

    assert _rodar(["pipeline", "--recursos", "ibge.municipios"], deps, dbt) == 1


def test_pipeline_tse_coleta_falha_nao_executa_candidato(deps, tmp_path, monkeypatch):
    import json
    from dataclasses import asdict, replace

    from coletor import cli
    from coletor.execucao import ResumoColetas
    from tests.test_tse_selecao import montar_vetor

    lago, selecao = montar_vetor(tmp_path)
    deps.config = replace(deps.config, lago=lago)
    arquivo = tmp_path / "selecao.json"
    arquivo.write_text(json.dumps(asdict(selecao)))
    monkeypatch.setattr(cli, "rodar", lambda *a: ResumoColetas(falhas=1))

    def dbt(*a, **kw):
        raise AssertionError("coleta falha impede build candidato")

    assert _rodar(["pipeline", "--grupo", "tse", "--selecao-tse", str(arquivo)], deps, dbt) == 1
    assert not (lago / "estado/tse/vigente.json").exists()


def test_pipeline_tse_expoe_execucao_aprovada(deps, tmp_path, monkeypatch, capsys):
    import json
    from dataclasses import asdict, replace

    from coletor import cli
    from coletor.execucao import ResumoColetas
    from tests.test_tse_pipeline import executor_sintetico
    from tests.test_tse_selecao import montar_vetor

    lago, selecao = montar_vetor(tmp_path)
    deps.config = replace(deps.config, lago=lago)
    arquivo = tmp_path / "selecao.json"
    arquivo.write_text(json.dumps(asdict(selecao)))
    monkeypatch.setattr(cli, "rodar", lambda *a: ResumoColetas())

    def dbt(diretorio, **kwargs):
        return executor_sintetico()(**kwargs)

    assert _rodar(["pipeline", "--grupo", "tse", "--selecao-tse", str(arquivo)], deps, dbt) == 0
    saida = capsys.readouterr().out
    assert "execucao_tse=" in saida
    assert (lago / "estado/tse/vigente.json").exists()
