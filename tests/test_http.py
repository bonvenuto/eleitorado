import hashlib

import httpx
import pytest

from coletor.http import ClienteHttp, ErroHttp


def test_baixar_grava_o_arquivo_e_calcula_o_hash(respx_mock, http, tmp_path):
    respx_mock.get("https://fonte/arquivo.zip").mock(
        return_value=httpx.Response(200, content=b"abc", headers={"Last-Modified": "ontem"})
    )
    download = http.baixar("https://fonte/arquivo.zip", tmp_path / "x")
    assert (tmp_path / "x").read_bytes() == b"abc"
    assert download.sha256 == hashlib.sha256(b"abc").hexdigest()
    assert (download.bytes, download.last_modified) == (3, "ontem")


def test_baixar_segue_redirecionamento_e_guarda_a_url_final(respx_mock, http, tmp_path):
    respx_mock.get("https://fonte/ceis/20261002").mock(
        return_value=httpx.Response(302, headers={"Location": "https://cdn/20261002_CEIS.zip"})
    )
    respx_mock.get("https://cdn/20261002_CEIS.zip").mock(
        return_value=httpx.Response(200, content=b"z")
    )
    download = http.baixar("https://fonte/ceis/20261002", tmp_path / "x")
    assert download.url_final == "https://cdn/20261002_CEIS.zip"


def test_repete_em_503_e_respeita_retry_after(respx_mock, tmp_path):
    esperas: list[float] = []
    cliente = ClienteHttp(dormir=esperas.append)
    rota = respx_mock.get("https://fonte/a").mock(
        side_effect=[
            httpx.Response(503, headers={"Retry-After": "7"}),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    resposta = cliente.obter_json("https://fonte/a")
    assert resposta.dados == {"ok": True}
    assert rota.call_count == 2
    assert esperas == [7.0]


def test_404_nao_e_repetido(respx_mock, http):
    rota = respx_mock.get("https://fonte/a").mock(return_value=httpx.Response(404))
    with pytest.raises(ErroHttp) as erro:
        http.obter_json("https://fonte/a")
    assert erro.value.status == 404
    assert rota.call_count == 1


def test_falha_de_transporte_esgota_as_tentativas(respx_mock):
    cliente = ClienteHttp(tentativas=3, dormir=lambda s: None)
    rota = respx_mock.get("https://fonte/a").mock(side_effect=httpx.ConnectError("recusada"))
    with pytest.raises(ErroHttp) as erro:
        cliente.obter_texto("https://fonte/a")
    assert erro.value.status is None
    assert rota.call_count == 3


def test_obter_json_envia_accept_json(respx_mock, http):
    rota = respx_mock.get("https://fonte/a").mock(return_value=httpx.Response(200, json=[]))
    http.obter_json("https://fonte/a", {"itens": 100})
    pedido = rota.calls.last.request
    assert pedido.headers["accept"] == "application/json"
    assert pedido.url.params["itens"] == "100"
