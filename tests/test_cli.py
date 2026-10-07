import httpx
import pytest

from coletor.cli import main
from coletor.dbt import ResultadoDbt
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
    assert len(warehouse.linhas["meta/fontes"]) == 30
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


def test_coletar_competencia_diaria(respx_mock, deps, warehouse):
    respx_mock.get("https://pncp.gov.br/api/consulta/v1/contratos").mock(
        return_value=httpx.Response(200, json={"data": [], "totalPaginas": 0})
    )
    assert _rodar(["coletar", "pncp.contratos", "--competencia", "2026-06-01"], deps) == 0
    [coleta] = warehouse.linhas["meta/coletas"]
    assert (coleta["recurso"], coleta["competencia"], coleta["status"]) == (
        "contratos",
        "2026-06-01",
        "carregada",
    )


def test_executar_sem_recursos_so_coleta_o_grupo_pedido(deps, warehouse, monkeypatch):
    pedidas = []

    def tarefas(recursos, historico, hoje):
        pedidas.append(sorted(rc.recurso.grupo for rc in recursos))
        return []

    monkeypatch.setattr("coletor.cli.tarefas_pendentes", tarefas)
    assert _rodar(["executar"], deps) == 0
    assert _rodar(["executar", "--grupo", "receita"], deps) == 0
    assert set(pedidas[0]) == {"diario"}
    assert set(pedidas[1]) == {"receita"}
    assert len(pedidas[1]) == 10


def test_bootstrap_tse_tres_chamadas_somente_um_ano(deps, monkeypatch):
    from coletor import cli

    chamadas = []

    def rodar(tarefas, *a, **kw):
        chamadas.extend(tarefas)
        return 0

    monkeypatch.setattr(cli, "_rodar_tarefas", rodar)
    for recurso in ("candidaturas", "bens", "contas"):
        assert _rodar(["coletar", f"tse.{recurso}", "--competencia", "2024"], deps) == 0
    assert len(chamadas) == 3
    assert {t.competencia.rotulo for t in chamadas} == {"2024"}
    assert sum(len(t.recurso.recurso.familias) for t in chamadas) == 6


def test_publicar_sem_flag_tse_somente_legado(deps, tmp_path, monkeypatch):
    import json
    from dataclasses import asdict, replace

    from coletor import cli, publicacao
    from coletor.tse import publicacao as c2
    from tests.test_tse_selecao import montar_vetor

    lago, selecao = montar_vetor(tmp_path)
    (lago / "estado/tse/vigente.json").write_text(json.dumps(asdict(selecao)))
    deps.config = replace(deps.config, lago=lago, publico=tmp_path / "publico")
    vistos = []

    def docs(d, t, p, argumentos=()):
        variaveis = json.loads(argumentos[argumentos.index("--vars") + 1])
        assert variaveis["tse_saida"].startswith(lago.as_posix())
        vistos.append("docs")
        return True

    monkeypatch.setattr(cli, "gerar_linhagem", docs)
    monkeypatch.setattr(publicacao, "R2Publicador", lambda *a: object())
    monkeypatch.setattr(publicacao, "publicar", lambda *a: vistos.append("legado"))
    monkeypatch.setattr(c2, "publicar_tse", lambda *a: pytest.fail("C2 sem flag"))
    env = {**ENV, **dict.fromkeys(["R2_CONTA", "R2_CHAVE_ID", "R2_SEGREDO", "R2_BUCKET"], "teste")}
    assert (
        main(["--fontes", str(RAIZ / "fontes"), "publicar"], fabrica=lambda c: deps, env=env) == 0
    )
    assert vistos == ["docs", "legado"]


def test_publicar_execucao_explicita_mesmas_vars_e_saida(deps, tmp_path, monkeypatch):
    import json
    from dataclasses import replace

    from coletor import cli, publicacao
    from coletor.tse import publicacao as c2
    from tests.test_tse_publicacao import candidata
    from tests.test_tse_selecao import montar_vetor

    lago, selecao = montar_vetor(tmp_path)
    preparada, selecao, recibo = candidata(lago, selecao, "explicita")
    deps.config = replace(deps.config, lago=lago, publico=tmp_path / "publico")
    prep = json.loads((preparada.parent / "preparacao.json").read_bytes())
    monkeypatch.setattr("coletor.site.gerar_site", lambda *a: 0)
    assert (
        main(
            ["--target", "ci", "site"],
            env={"ELEITORADO_LAGO": str(lago), "ELEITORADO_PUBLICO": str(deps.config.publico)},
            dbt=lambda *a: ResultadoDbt("sucesso", 0),
        )
        == 0
    )
    assert json.loads((preparada.parent / "preparacao.json").read_bytes()) == prep
    vistos = []

    def docs(d, t, p, argumentos=()):
        assert t == prep["target"]
        assert json.loads(argumentos[argumentos.index("--vars") + 1]) == prep["vars"]
        vistos.append("docs")
        return True

    def publicar_c2(pub, pasta, sel, agora, versao, rec):
        assert pasta == preparada and sel == selecao and rec == recibo
        vistos.append("C2")

    monkeypatch.setattr(cli, "gerar_linhagem", docs)
    monkeypatch.setattr(publicacao, "R2Publicador", lambda *a: object())
    monkeypatch.setattr(publicacao, "publicar", lambda *a: vistos.append("legado"))
    monkeypatch.setattr(c2, "publicar_tse", publicar_c2)
    env = {**ENV, **dict.fromkeys(["R2_CONTA", "R2_CHAVE_ID", "R2_SEGREDO", "R2_BUCKET"], "teste")}
    assert (
        main(
            [
                "--fontes",
                str(RAIZ / "fontes"),
                "--target",
                "ci",
                "publicar",
                "--execucao-tse",
                "explicita",
            ],
            fabrica=lambda c: deps,
            env=env,
        )
        == 0
    )
    assert vistos == ["docs", "legado", "C2"]
