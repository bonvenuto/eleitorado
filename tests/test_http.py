import hashlib

import httpx
import pytest

from coletor.http import SUFIXOS_OFICIAIS, ClienteHttp, ErroHttp, host_permitido


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


def test_obter_json_com_204_devolve_dados_vazios(respx_mock, http):
    respx_mock.get("https://api.exemplo/x").mock(return_value=httpx.Response(204))
    resposta = http.obter_json("https://api.exemplo/x")
    assert (resposta.status, resposta.dados) == (204, None)


def test_host_permitido_por_sufixo():
    assert host_permitido("pncp.gov.br", SUFIXOS_OFICIAIS)
    assert host_permitido("dadosabertos.camara.leg.br", SUFIXOS_OFICIAIS)
    assert not host_permitido("169.254.169.254", SUFIXOS_OFICIAIS)
    assert not host_permitido("gov.br.exemplo.com", SUFIXOS_OFICIAIS)
    assert not host_permitido("exemplogov.br", SUFIXOS_OFICIAIS)


def test_redirecionamento_para_host_nao_oficial_e_bloqueado(respx_mock, tmp_path):
    cliente = ClienteHttp(dormir=lambda s: None, sufixos_permitidos=SUFIXOS_OFICIAIS)
    respx_mock.get("https://pncp.gov.br/a").mock(
        return_value=httpx.Response(302, headers={"Location": "http://169.254.169.254/x"})
    )
    destino = respx_mock.get("http://169.254.169.254/x").mock(return_value=httpx.Response(200))
    with pytest.raises(ErroHttp, match="host não permitido"):
        cliente.obter_json("https://pncp.gov.br/a")
    assert destino.call_count == 0


def test_host_oficial_passa(respx_mock):
    cliente = ClienteHttp(dormir=lambda s: None, sufixos_permitidos=SUFIXOS_OFICIAIS)
    respx_mock.get("https://pncp.gov.br/a").mock(return_value=httpx.Response(200, json=[1]))
    assert cliente.obter_json("https://pncp.gov.br/a").dados == [1]


def test_422_e_repetido_como_transitorio(respx_mock):
    cliente = ClienteHttp(dormir=lambda s: None)
    rota = respx_mock.get("https://fonte/a").mock(
        side_effect=[httpx.Response(422), httpx.Response(200, json=[1])]
    )
    assert cliente.obter_json("https://fonte/a").dados == [1]
    assert rota.call_count == 2


def _parcial(conteudo: bytes, total: int, status: int = 200) -> httpx.Response:
    """Resposta que anuncia `total` bytes e entrega só `conteudo` (conexão derrubada)."""
    return httpx.Response(
        status, headers={"Content-Length": str(total)}, stream=httpx.ByteStream(conteudo)
    )


def test_baixar_retomando_continua_de_onde_parou(respx_mock, http, tmp_path):
    rota = respx_mock.get("https://arquivos.receitafederal.gov.br/x.zip")
    rota.side_effect = [_parcial(b"abcd", 10), _parcial(b"efghij", 6, status=206)]
    download = http.baixar_retomando(
        "https://arquivos.receitafederal.gov.br/x.zip", tmp_path / "x", "token"
    )
    assert (tmp_path / "x").read_bytes() == b"abcdefghij"
    assert download.sha256 == hashlib.sha256(b"abcdefghij").hexdigest()
    assert download.bytes == 10
    assert rota.calls[1].request.headers["Range"] == "bytes=4-"
    assert rota.calls[0].request.headers["Authorization"].startswith("Basic ")


def test_baixar_retomando_recusa_servidor_que_ignora_o_range(respx_mock, http, tmp_path):
    rota = respx_mock.get("https://arquivos.receitafederal.gov.br/x.zip")
    rota.side_effect = [_parcial(b"abcd", 10), _parcial(b"abcdefghij", 10)]
    with pytest.raises(ErroHttp, match="ignorou o Range"):
        http.baixar_retomando("https://arquivos.receitafederal.gov.br/x.zip", tmp_path / "x")


def test_baixar_retomando_repete_falha_de_transporte_e_desiste(respx_mock, http, tmp_path):
    rota = respx_mock.get("https://arquivos.receitafederal.gov.br/x.zip")
    rota.side_effect = httpx.ReadError("caiu")
    with pytest.raises(ErroHttp, match="falha de transporte"):
        http.baixar_retomando(
            "https://arquivos.receitafederal.gov.br/x.zip", tmp_path / "x", tentativas=3
        )
    assert rota.call_count == 3


def test_baixar_retomando_nao_repete_404(respx_mock, http, tmp_path):
    rota = respx_mock.get("https://arquivos.receitafederal.gov.br/x.zip")
    rota.mock(return_value=httpx.Response(404))
    with pytest.raises(ErroHttp) as erro:
        http.baixar_retomando("https://arquivos.receitafederal.gov.br/x.zip", tmp_path / "x")
    assert erro.value.status == 404
    assert rota.call_count == 1


def test_listar_webdav_devolve_pastas_e_arquivos_sem_a_propria_pasta(respx_mock, http):
    corpo = (
        '<?xml version="1.0"?><d:multistatus xmlns:d="DAV:">'
        "<d:response><d:href>/webdav/</d:href><d:propstat><d:prop>"
        "<d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat></d:response>"
        "<d:response><d:href>/webdav/2026-09/</d:href><d:propstat><d:prop>"
        "<d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat></d:response>"
        "<d:response><d:href>/webdav/S%C3%B3cios.zip</d:href><d:propstat><d:prop>"
        "<d:resourcetype/><d:getcontentlength>42</d:getcontentlength></d:prop></d:propstat>"
        "</d:response></d:multistatus>"
    )
    rota = respx_mock.route(method="PROPFIND", url="https://arquivos.receitafederal.gov.br/webdav/")
    rota.mock(return_value=httpx.Response(207, text=corpo))
    itens = http.listar_webdav("https://arquivos.receitafederal.gov.br/webdav/", "token")
    assert [(i.nome, i.pasta, i.tamanho) for i in itens] == [
        ("2026-09", True, None),
        ("Sócios.zip", False, 42),
    ]
    assert rota.calls[0].request.headers["Depth"] == "1"


@pytest.mark.parametrize(
    ("host", "permitido"),
    [
        ("tse.jus.br", True),
        ("cdn.tse.jus.br", True),
        ("outro.jus.br", False),
        ("evil-tse.jus.br", False),
        ("tse.jus.br.evil.gov", False),
    ],
)
def test_tse_e_subdominio_permitidos(host, permitido):
    assert host_permitido(host, SUFIXOS_OFICIAIS) is permitido


def test_tse_segue_redirecionamento_para_subdominio(respx_mock):
    cliente = ClienteHttp(dormir=lambda s: None, sufixos_permitidos=SUFIXOS_OFICIAIS)
    respx_mock.get("https://tse.jus.br/a").mock(
        return_value=httpx.Response(302, headers={"Location": "https://cdn.tse.jus.br/a"})
    )
    respx_mock.get("https://cdn.tse.jus.br/a").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    try:
        resposta = cliente.obter_json("https://tse.jus.br/a")
        assert resposta.dados == {"ok": True}
        assert resposta.url_final == "https://cdn.tse.jus.br/a"
    finally:
        cliente.fechar()


@pytest.mark.parametrize("metodo", ["obter_json", "baixar"])
def test_tse_bloqueia_host_intermediario_antes_de_voltar_a_host_permitido(
    respx_mock, tmp_path, metodo
):
    cliente = ClienteHttp(dormir=lambda s: None, sufixos_permitidos=SUFIXOS_OFICIAIS)
    origem = respx_mock.get("https://tse.jus.br/a").mock(
        return_value=httpx.Response(302, headers={"Location": "https://outro.jus.br/a"})
    )
    proibido = respx_mock.get("https://outro.jus.br/a").mock(
        return_value=httpx.Response(302, headers={"Location": "https://cdn.tse.jus.br/a"})
    )
    final = respx_mock.get("https://cdn.tse.jus.br/a").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    try:
        with pytest.raises(ErroHttp, match="host não permitido: outro.jus.br") as erro:
            if metodo == "obter_json":
                cliente.obter_json("https://tse.jus.br/a")
            else:
                cliente.baixar("https://tse.jus.br/a", tmp_path / "x")
        assert erro.value.url == "https://outro.jus.br/a"
        assert origem.call_count == 1
        assert proibido.call_count == 0
        assert final.call_count == 0
    finally:
        cliente.fechar()


def test_tse_bloqueia_host_intermediario_na_retomada(respx_mock, tmp_path):
    cliente = ClienteHttp(dormir=lambda s: None, sufixos_permitidos=SUFIXOS_OFICIAIS)
    origem = respx_mock.get("https://tse.jus.br/a").mock(
        side_effect=[
            _parcial(b"abcd", 10),
            httpx.Response(302, headers={"Location": "https://outro.jus.br/a"}),
        ]
    )
    proibido = respx_mock.get("https://outro.jus.br/a").mock(
        return_value=httpx.Response(302, headers={"Location": "https://cdn.tse.jus.br/a"})
    )
    final = respx_mock.get("https://cdn.tse.jus.br/a").mock(
        return_value=_parcial(b"efghij", 6, status=206)
    )
    try:
        with pytest.raises(ErroHttp, match="host não permitido: outro.jus.br") as erro:
            cliente.baixar_retomando("https://tse.jus.br/a", tmp_path / "x")
        assert erro.value.url == "https://outro.jus.br/a"
        assert (tmp_path / "x").read_bytes() == b"abcd"
        assert origem.call_count == 2
        assert origem.calls[1].request.headers["Range"] == "bytes=4-"
        assert proibido.call_count == 0
        assert final.call_count == 0
    finally:
        cliente.fechar()
