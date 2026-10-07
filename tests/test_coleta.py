from datetime import UTC, date, datetime

import httpx

from coletor.coleta import coletar, recarregar
from coletor.competencias import Competencia
from coletor.execucao import ResumoColetas
from coletor.manifesto import RecursoCompleto
from coletor.meta import HistoricoColetas, Sucesso
from tests.amostras import CNEP_CSV, PAGINA_CGU, recurso, zip_com

PAGINA = "https://portaldatransparencia.gov.br/download-de-dados/cnep"
CNEP = RecursoCompleto("cgu", recurso())


def _mock_cnep(respx_mock, conteudo: bytes = CNEP_CSV.encode("cp1252")):
    respx_mock.get(PAGINA).mock(return_value=httpx.Response(200, text=PAGINA_CGU))
    respx_mock.get(f"{PAGINA}/20261002").mock(
        return_value=httpx.Response(200, content=zip_com({"20261002_CNEP.csv": conteudo}))
    )


def test_coleta_nova_arquiva_converte_e_carrega(respx_mock, deps, armazenamento, warehouse):
    _mock_cnep(respx_mock)
    registro = coletar(CNEP, None, HistoricoColetas(), deps, "exec-1")
    assert registro.status == "carregada", registro.erro
    assert registro.competencia == "2026-10-02"
    assert registro.linhas == 2
    assert registro.esquema_alterado is False
    assert registro.arquivo_original.startswith(
        "gs://bucket-teste/dev/originais/cgu/cnep/competencia=2026-10-02/20261003T103000_"
    )
    assert registro.arquivo_original.endswith(".bin")
    assert registro.arquivo_carga == f"raw/cgu/cnep/20261002/{registro.coleta_id}.parquet"
    tabela = warehouse.particoes[("raw/cgu/cnep", "20261002")]
    assert tabela.column("_arquivo_original").to_pylist() == [registro.arquivo_original] * 2
    particionamento = warehouse.particionamentos["raw/cgu/cnep"]
    assert (particionamento.granularidade, particionamento.expiracao_dias) == ("DAY", 60)


def test_mesmo_conteudo_da_ultima_coleta_nao_e_recarregado(respx_mock, deps, armazenamento):
    _mock_cnep(respx_mock)
    historico = HistoricoColetas()
    primeiro = coletar(CNEP, None, historico, deps, "exec-1")
    historico.registrar(primeiro)
    objetos_antes = dict(armazenamento.objetos)
    segundo = coletar(CNEP, None, historico, deps, "exec-2")
    assert segundo.status == "sem_alteracao"
    assert segundo.sha256_conteudo == primeiro.sha256_conteudo
    assert armazenamento.objetos == objetos_antes


def test_forcar_recarrega_mesmo_sem_alteracao(respx_mock, deps):
    _mock_cnep(respx_mock)
    historico = HistoricoColetas()
    historico.registrar(coletar(CNEP, None, historico, deps, "exec-1"))
    deps.agora = lambda: datetime(2026, 10, 3, 10, 31, tzinfo=UTC)
    assert coletar(CNEP, None, historico, deps, "exec-2", forcar=True).status == "carregada"


def test_falha_na_carga_vira_registro_sem_carga_parcial(respx_mock, deps, warehouse):
    _mock_cnep(respx_mock)
    warehouse.falha_na_carga = RuntimeError("BigQuery fora do ar")
    registro = coletar(CNEP, None, HistoricoColetas(), deps, "exec-1")
    assert registro.status == "falha"
    assert registro.erro == "RuntimeError: BigQuery fora do ar"
    assert warehouse.particoes == {}


def test_mudanca_de_cabecalho_marca_esquema_alterado(respx_mock, deps):
    _mock_cnep(respx_mock)
    historico = HistoricoColetas()
    primeiro = coletar(CNEP, None, historico, deps, "exec-1")
    historico.registrar(primeiro)
    novo_csv = CNEP_CSV.replace('"OBSERVAÇÕES"', '"OBSERVACAO NOVA"')
    respx_mock.get(f"{PAGINA}/20261002").mock(
        return_value=httpx.Response(
            200, content=zip_com({"20261002_CNEP.csv": novo_csv.encode("cp1252")})
        )
    )
    deps.agora = lambda: datetime(2026, 10, 3, 10, 31, tzinfo=UTC)
    segundo = coletar(CNEP, None, historico, deps, "exec-2")
    assert segundo.status == "carregada"
    assert segundo.esquema_alterado is True


def _ceap() -> RecursoCompleto:
    return RecursoCompleto(
        "camara",
        recurso(
            id="ceap",
            url="https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip",
            publicacao="por_competencia",
            competencia={"tipo": "ano", "inicio": 2008},
            cadencia={"corrente": "diaria", "anteriores": "semanal"},
            formato={"tipo": "csv", "compressao": "zip", "arquivo": "Ano-{ano}.csv"},
        ),
    )


def test_ano_corrente_ainda_nao_publicado_no_primeiro_trimestre(respx_mock, deps):
    respx_mock.get("https://www.camara.leg.br/cotas/Ano-2027.csv.zip").mock(
        return_value=httpx.Response(404)
    )
    deps.agora = lambda: datetime(2027, 1, 2, 10, 30, tzinfo=UTC)
    registro = coletar(_ceap(), Competencia.de_ano(2027), HistoricoColetas(), deps, "exec-1")
    assert registro.status == "nao_publicada"
    deps.agora = lambda: datetime(2027, 5, 2, 10, 30, tzinfo=UTC)
    tardio = coletar(_ceap(), Competencia.de_ano(2027), HistoricoColetas(), deps, "exec-2")
    assert tardio.status == "falha"


def test_por_competencia_carrega_na_particao_anual(respx_mock, deps, warehouse):
    respx_mock.get("https://www.camara.leg.br/cotas/Ano-2025.csv.zip").mock(
        return_value=httpx.Response(200, content=zip_com({"Ano-2025.csv": b'"A";"B"\n"1";"2"\n'}))
    )
    registro = coletar(_ceap(), Competencia.de_ano(2025), HistoricoColetas(), deps, "exec-1")
    assert registro.status == "carregada", registro.erro
    assert ("raw/camara/ceap", "2025") in warehouse.particoes
    particionamento = warehouse.particionamentos["raw/camara/ceap"]
    assert (particionamento.granularidade, particionamento.expiracao_dias) == ("YEAR", None)


def test_recarga_para_replay_usa_o_original_e_nao_expira(respx_mock, deps, warehouse):
    _mock_cnep(respx_mock)
    original = coletar(CNEP, None, HistoricoColetas(), deps, "exec-1")
    registro = recarregar(
        CNEP,
        Competencia.de_dia(date(2026, 10, 2)),
        original.arquivo_original,
        HistoricoColetas(),
        deps,
        "exec-2",
        "replay",
    )
    assert registro.status == "recarregada", registro.erro
    assert registro.sha256_conteudo == original.sha256_conteudo
    assert ("replay/raw/cgu/cnep", "20261002") in warehouse.particoes
    assert warehouse.particionamentos["replay/raw/cgu/cnep"].expiracao_dias is None


def test_coleta_forcada_duas_vezes_no_mesmo_segundo_reaproveita_o_original(
    respx_mock, deps, armazenamento
):
    _mock_cnep(respx_mock)
    historico = HistoricoColetas()
    primeiro = coletar(CNEP, None, historico, deps, "exec-1", forcar=True)
    segundo = coletar(CNEP, None, historico, deps, "exec-2", forcar=True)
    assert (primeiro.status, segundo.status) == ("carregada", "carregada")
    assert primeiro.arquivo_original == segundo.arquivo_original
    originais = [c for c in armazenamento.objetos if "/originais/" in c]
    assert len(originais) == 1


def test_html_de_erro_no_lugar_do_zip_vira_falha(respx_mock, deps, warehouse):
    respx_mock.get(PAGINA).mock(return_value=httpx.Response(200, text=PAGINA_CGU))
    respx_mock.get(f"{PAGINA}/20261002").mock(
        return_value=httpx.Response(200, text="<html>Serviço indisponível</html>")
    )
    registro = coletar(CNEP, None, HistoricoColetas(), deps, "exec-1")
    assert registro.status == "falha"
    assert registro.erro.startswith("BadZipFile")
    assert warehouse.particoes == {}


def test_json_invalido_na_api_vira_falha(respx_mock, deps):
    municipios = RecursoCompleto(
        "ibge",
        recurso(
            id="municipios",
            adaptador="api_json",
            url="https://servicodados.ibge.gov.br/api/v1/localidades/municipios",
            competencia={"tipo": "data_coleta"},
            formato={"tipo": "json"},
        ),
    )
    respx_mock.get("https://servicodados.ibge.gov.br/api/v1/localidades/municipios").mock(
        return_value=httpx.Response(200, text="<html>erro</html>")
    )
    registro = coletar(
        municipios, Competencia.de_dia(date(2026, 10, 3)), HistoricoColetas(), deps, "e"
    )
    assert registro.status == "falha"
    assert "JSONDecodeError" in registro.erro


def test_execucao_interrompida_antes_da_carga_e_refeita_na_seguinte(respx_mock, deps, warehouse):
    _mock_cnep(respx_mock)
    historico = HistoricoColetas()
    warehouse.falha_na_carga = RuntimeError("processo interrompido")
    interrompida = coletar(CNEP, None, historico, deps, "exec-1")
    historico.registrar(interrompida)  # falha não conta como sucesso
    warehouse.falha_na_carga = None
    deps.agora = lambda: datetime(2026, 10, 3, 11, 0, tzinfo=UTC)
    refeita = coletar(CNEP, None, historico, deps, "exec-2")
    assert (interrompida.status, refeita.status) == ("falha", "carregada")
    assert ("raw/cgu/cnep", "20261002") in warehouse.particoes


def test_resumo_conta_status_e_so_falha_derruba_o_sucesso():
    resumo = ResumoColetas()
    for status in ["carregada", "sem_alteracao", "nao_publicada"]:
        resumo.contar(status)
    assert resumo.sucesso
    resumo.contar("falha")
    assert (resumo.carregadas, resumo.sem_alteracao, resumo.nao_publicadas, resumo.falhas) == (
        1,
        1,
        1,
        1,
    )
    assert not resumo.sucesso


def test_mes_recente_nao_publicado():
    from coletor.coleta import nao_publicada
    from coletor.http import ErroHttp

    mensal = recurso(
        publicacao="por_competencia",
        competencia={"tipo": "mes", "inicio": 2013},
        cadencia={"corrente": "semanal", "anteriores": "mensal"},
    )
    hoje = date(2026, 10, 5)
    erro = ErroHttp(url="u", status=403, mensagem="x")
    assert nao_publicada(mensal, Competencia.de_mes(2026, 8), erro, hoje)
    assert not nao_publicada(mensal, Competencia.de_mes(2026, 6), erro, hoje)  # antigo: falha
    assert not nao_publicada(
        mensal, Competencia.de_mes(2026, 8), ErroHttp(url="u", status=500, mensagem="x"), hoje
    )


def test_bloqueio_anti_robo_vira_adiada(respx_mock, deps):
    respx_mock.get(url__startswith="https://portaldatransparencia.gov.br").mock(
        return_value=httpx.Response(405, text="captcha")
    )
    registro = coletar(CNEP, None, HistoricoColetas(), deps, "e1")
    assert (registro.status, registro.http_status) == ("adiada", 405)


def _webdav(respx_mock, competencias: list[str]):
    from tests.amostras import RAIZ_WEBDAV, propfind_webdav

    itens = [(f"{c}/", None) for c in competencias]
    respx_mock.route(method="PROPFIND", url=RAIZ_WEBDAV).mock(
        return_value=httpx.Response(207, text=propfind_webdav("/public.php/webdav/", itens))
    )


def test_competencia_da_receita_ja_coletada_nao_e_baixada(respx_mock, deps):
    from tests.amostras import recurso_webdav

    _webdav(respx_mock, ["2026-08", "2026-09"])
    historico = HistoricoColetas(
        {
            ("rfb.empresas", "2026-09"): Sucesso(
                datetime(2026, 9, 20, tzinfo=UTC), "sha-do-recorte", date(2026, 9, 1), None
            )
        }
    )
    rc = RecursoCompleto("rfb", recurso_webdav())
    registro = coletar(rc, None, historico, deps, "exec-1")
    assert (registro.status, registro.competencia) == ("sem_alteracao", "2026-09")
    assert registro.sha256_conteudo == "sha-do-recorte"  # a próxima execução também pula
    assert [c.request.method for c in respx_mock.calls] == ["PROPFIND"]  # nada baixado


def test_recorte_da_receita_carrega_na_particao_mensal_sem_expirar(
    respx_mock, deps, warehouse, tmp_path, monkeypatch
):
    import duckdb

    from tests.amostras import RAIZ_WEBDAV, propfind_webdav, recurso_webdav

    (tmp_path / "lago" / "rfb").mkdir(parents=True)
    duckdb.sql(
        "copy (select '11222333' as raiz) "
        f"to '{(tmp_path / 'lago' / 'rfb' / 'raizes.parquet').as_posix()}' (format parquet)"
    )
    monkeypatch.setenv("ELEITORADO_LAGO", str(tmp_path / "lago"))
    _webdav(respx_mock, ["2026-09"])
    conteudo = zip_com({"K.EMPRECSV": b'"11222333";"A";"01"\n"99999999";"B";"05"\n'})
    pasta = f"{RAIZ_WEBDAV}2026-09/"
    respx_mock.route(method="PROPFIND", url=pasta).mock(
        return_value=httpx.Response(
            207,
            text=propfind_webdav("/public.php/webdav/2026-09/", [("Empresas0.zip", len(conteudo))]),
        )
    )
    respx_mock.get(f"{pasta}Empresas0.zip").mock(return_value=httpx.Response(200, content=conteudo))
    registro = coletar(
        RecursoCompleto("rfb", recurso_webdav()), None, HistoricoColetas(), deps, "e"
    )
    assert registro.status == "carregada", registro.erro
    assert (registro.competencia, registro.linhas) == ("2026-09", 1)
    assert ("raw/rfb/empresas", "202609") in warehouse.particoes
    particionamento = warehouse.particionamentos["raw/rfb/empresas"]
    assert (particionamento.granularidade, particionamento.expiracao_dias) == ("MONTH", None)
    assert registro.parametros["arquivos"][0]["linhas_mantidas"] == 1
