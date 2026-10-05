import gzip
import json
from datetime import date

import httpx
import pytest

from coletor.adaptadores import api_json
from coletor.adaptadores.base import ErroColeta
from coletor.competencias import Competencia
from tests.amostras import json_bytes, pagina_deputados, recurso, senadores_json

HOJE = date(2026, 10, 3)


def _recurso_deputados():
    return recurso(
        id="deputados",
        adaptador="api_json",
        url="https://dadosabertos.camara.leg.br/api/v2/deputados",
        parametros={"itens": 100},
        competencia={"tipo": "data_coleta"},
        cadencia={"corrente": "semanal"},
        formato={"tipo": "json"},
        paginacao="links_next",
        iteracao={"parametro": "idLegislatura", "valores": "legislaturas", "inicio": 56},
        registros="dados",
    )


def test_api_pagina_por_links_e_itera_legislaturas(respx_mock, http, tmp_path):
    base = "https://dadosabertos.camara.leg.br/api/v2/deputados"
    proxima = f"{base}?idLegislatura=56&pagina=2&itens=100"
    # rotas mais específicas primeiro: o padrão de params do respx casa por "contém"
    respx_mock.get(base, params={"idLegislatura": "56", "pagina": "2"}).mock(
        return_value=httpx.Response(200, json=pagina_deputados([3], None))
    )
    respx_mock.get(base, params={"idLegislatura": "56", "itens": "100"}).mock(
        return_value=httpx.Response(200, json=pagina_deputados([1, 2], proxima))
    )
    respx_mock.get(base, params={"idLegislatura": "57"}).mock(
        return_value=httpx.Response(200, json=pagina_deputados([4], None))
    )
    rec = _recurso_deputados()
    extracao = api_json.extrair(rec, Competencia.de_dia(HOJE), tmp_path, http, HOJE)
    preparado = api_json.preparar(rec, extracao.competencia, extracao.arquivo_original, tmp_path)
    assert [r["id"] for r in preparado.registros] == [1, 2, 3, 4]
    assert extracao.parametros["iteracao"]["valores"] == [56, 57]
    with gzip.open(extracao.arquivo_original, "rt", encoding="utf-8") as paginas:
        assert len(paginas.readlines()) == 3


def test_api_com_metadado_volatil_tem_o_mesmo_hash_de_conteudo(respx_mock, http, tmp_path):
    rec = recurso(
        id="senadores",
        adaptador="api_json",
        url="https://legis.senado.leg.br/dadosabertos/senador/lista/legislatura/53/{legislatura}.json",
        competencia={"tipo": "data_coleta"},
        cadencia={"corrente": "semanal"},
        formato={"tipo": "json"},
        registros="ListaParlamentarLegislatura.Parlamentares.Parlamentar",
    )
    url = "https://legis.senado.leg.br/dadosabertos/senador/lista/legislatura/53/57.json"
    hashes = []
    for indice, versao in enumerate(["03/10/2026 15:20:06", "04/10/2026 08:00:00"]):
        respx_mock.get(url).mock(
            return_value=httpx.Response(200, content=json_bytes(senadores_json(versao)))
        )
        pasta = tmp_path / str(indice)
        pasta.mkdir()
        extracao = api_json.extrair(rec, Competencia.de_dia(HOJE), pasta, http, HOJE)
        preparado = api_json.preparar(rec, extracao.competencia, extracao.arquivo_original, pasta)
        assert len(preparado.registros) == 2
        hashes.append((extracao.sha256_arquivo, preparado.sha256_conteudo))
    assert hashes[0][0] != hashes[1][0]
    assert hashes[0][1] == hashes[1][1]


def test_registros_unicos_viram_lista_e_caminho_ausente_falha():
    assert api_json.extrair_registros({"a": {"b": {"x": 1}}}, "a.b") == [{"x": 1}]
    assert api_json.extrair_registros({"a": None}, "a") == []
    assert api_json.extrair_registros([{"id": 1}], None) == [{"id": 1}]  # IBGE e CEAPS
    with pytest.raises(ErroColeta, match="parou em 'c'"):
        api_json.extrair_registros({"a": {"b": []}}, "a.c")


def test_paginacao_em_laco_e_interrompida(respx_mock, http, tmp_path):
    def pagina_que_aponta_para_si_mesma(request: httpx.Request) -> httpx.Response:
        # mesma URL com os parâmetros em outra ordem
        proxima = str(request.url.copy_with(params=sorted(request.url.params.multi_items())))
        return httpx.Response(200, json=pagina_deputados([1], proxima))

    base = "https://dadosabertos.camara.leg.br/api/v2/deputados"
    respx_mock.get(url__startswith=base).mock(side_effect=pagina_que_aponta_para_si_mesma)
    rec = _recurso_deputados()
    extracao = api_json.extrair(rec, Competencia.de_dia(HOJE), tmp_path, http, HOJE)
    with gzip.open(extracao.arquivo_original, "rt", encoding="utf-8") as paginas:
        linhas = [json.loads(linha) for linha in paginas]
    assert len(linhas) == 2  # uma página por legislatura; o link para si mesma não é seguido


def test_adaptador_e_escolhido_pelo_manifesto():
    from coletor.adaptadores import adaptador_para, arquivo

    assert adaptador_para(recurso()) is arquivo
    assert adaptador_para(_recurso_deputados()) is api_json


def _pncp(**sobrescritas):
    return recurso(
        adaptador="api_json",
        url="https://pncp.exemplo/api/contratos",
        parametros={"dataInicial": "{data}", "dataFinal": "{data}", "tamanhoPagina": 500},
        publicacao="por_competencia",
        competencia={"tipo": "dia", "inicio": 2021},
        cadencia={"corrente": "semanal", "anteriores": "anual"},
        formato={"tipo": "json"},
        paginacao="pagina_total",
        registros="data",
        **sobrescritas,
    )


def test_pagina_total_percorre_todas_as_paginas(respx_mock, http, tmp_path):
    rota = respx_mock.get("https://pncp.exemplo/api/contratos")
    rota.side_effect = [
        httpx.Response(200, json={"data": [{"id": 1}], "totalPaginas": 2}),
        httpx.Response(200, json={"data": [{"id": 2}], "totalPaginas": 2}),
    ]
    regra = _pncp()
    competencia = Competencia.de_dia(date(2026, 6, 1))
    extracao = api_json.extrair(regra, competencia, tmp_path, http, date(2026, 6, 2))
    preparado = api_json.preparar(regra, competencia, extracao.arquivo_original, tmp_path)
    assert [r["id"] for r in preparado.registros] == [1, 2]
    pedidas = [dict(chamada.request.url.params) for chamada in rota.calls]
    assert pedidas == [
        {"dataInicial": "20260601", "dataFinal": "20260601", "tamanhoPagina": "500", "pagina": "1"},
        {"dataInicial": "20260601", "dataFinal": "20260601", "tamanhoPagina": "500", "pagina": "2"},
    ]


def test_pagina_total_com_resposta_vazia(respx_mock, http, tmp_path):
    respx_mock.get("https://pncp.exemplo/api/contratos").mock(return_value=httpx.Response(204))
    regra = _pncp()
    competencia = Competencia.de_dia(date(2026, 6, 1))
    extracao = api_json.extrair(regra, competencia, tmp_path, http, date(2026, 6, 2))
    preparado = api_json.preparar(regra, competencia, extracao.arquivo_original, tmp_path)
    assert preparado.registros == []
