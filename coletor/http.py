"""Cliente HTTP com retentativas e download em streaming."""

from __future__ import annotations

import hashlib
import random
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, TypeVar
from urllib.parse import unquote

import httpx

# 422: o PNCP devolve 422 transitório numa página que responde 200 logo depois
STATUS_RETENTAVEIS = frozenset({422, 429, 500, 502, 503, 504})
USER_AGENT = "eleitorado-coletor/0.1"

# Fontes oficiais: toda requisição (inclusive o destino de um redirecionamento ou o link "next"
# de uma API) precisa ir para um destes domínios, o que impede a coleta de ser desviada para
# outro host.
SUFIXOS_OFICIAIS = (".gov.br", ".leg.br")


def host_permitido(host: str, sufixos: tuple[str, ...]) -> bool:
    return any(host == sufixo.lstrip(".") or host.endswith(sufixo) for sufixo in sufixos)


T = TypeVar("T")


class ErroHttp(Exception):
    def __init__(self, url: str, status: int | None, mensagem: str) -> None:
        super().__init__(f"{mensagem} (status={status}, url={url})")
        self.url = url
        self.status = status


class _RespostaComErro(Exception):
    def __init__(self, resposta: httpx.Response) -> None:
        super().__init__(resposta.status_code)
        self.resposta = resposta


@dataclass(frozen=True)
class Download:
    url_final: str
    status: int
    last_modified: str | None
    etag: str | None
    bytes: int
    sha256: str


@dataclass(frozen=True)
class ItemWebdav:
    nome: str  # último segmento do caminho, sem a barra final
    pasta: bool
    tamanho: int | None


@dataclass(frozen=True)
class RespostaJson:
    url_final: str
    status: int
    corpo: bytes
    dados: Any


class ClienteHttp:
    def __init__(
        self,
        tentativas: int = 5,
        espera_base: float = 2.0,
        espera_maxima: float = 60.0,
        dormir: Callable[[float], None] = time.sleep,
        transporte: httpx.BaseTransport | None = None,
        sufixos_permitidos: tuple[str, ...] | None = None,
    ) -> None:
        self._tentativas = tentativas
        self._espera_base = espera_base
        self._espera_maxima = espera_maxima
        self._dormir = dormir
        self.sufixos_permitidos = sufixos_permitidos
        self._cliente = httpx.Client(
            timeout=httpx.Timeout(120.0, connect=10.0),
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
            transport=transporte,
            event_hooks={"request": [self._verificar_host]},
        )

    def fechar(self) -> None:
        self._cliente.close()

    def baixar(self, url: str, destino: Path) -> Download:
        def tentativa() -> Download:
            resumo = hashlib.sha256()
            total = 0
            with self._cliente.stream("GET", url) as resposta:
                self._verificar(resposta)
                with destino.open("wb") as arquivo:
                    for bloco in resposta.iter_bytes():
                        arquivo.write(bloco)
                        resumo.update(bloco)
                        total += len(bloco)
                return Download(
                    url_final=str(resposta.url),
                    status=resposta.status_code,
                    last_modified=resposta.headers.get("last-modified"),
                    etag=resposta.headers.get("etag"),
                    bytes=total,
                    sha256=resumo.hexdigest(),
                )

        return self._com_retentativas(url, tentativa)

    def baixar_retomando(
        self, url: str, destino: Path, usuario: str | None = None, tentativas: int = 20
    ) -> Download:
        """Download de arquivo grande que retoma de onde parou (`Range`) quando a conexão cai.

        O servidor precisa informar o tamanho (`Content-Length`) e responder 206 à retomada; um
        200 numa retomada recomeçaria o arquivo do zero no meio dele, então vira erro.
        """
        auth = (usuario, "") if usuario is not None else None
        resumo = hashlib.sha256()
        recebido, total, falhas = 0, None, 0
        primeira: httpx.Response | None = None
        with destino.open("wb") as arquivo:
            while total is None or recebido < total:
                cabecalhos = {"Range": f"bytes={recebido}-"} if recebido else {}
                try:
                    with self._cliente.stream("GET", url, headers=cabecalhos, auth=auth) as r:
                        if r.status_code >= 400:
                            if r.status_code not in STATUS_RETENTAVEIS:
                                raise ErroHttp(str(r.url), r.status_code, "resposta HTTP de erro")
                            raise httpx.TransportError(f"status {r.status_code}")
                        if recebido and r.status_code != 206:
                            raise ErroHttp(str(r.url), r.status_code, "servidor ignorou o Range")
                        if total is None:
                            if "content-length" not in r.headers:
                                raise ErroHttp(str(r.url), r.status_code, "sem Content-Length")
                            total = int(r.headers["content-length"])
                            primeira = r
                        for bloco in r.iter_bytes(1 << 20):
                            arquivo.write(bloco)
                            resumo.update(bloco)
                            recebido += len(bloco)
                    if recebido < total:
                        raise httpx.TransportError(f"conexão encerrada em {recebido} de {total}")
                except httpx.TransportError as erro:
                    falhas += 1
                    if falhas >= tentativas:
                        raise ErroHttp(url, None, f"falha de transporte: {erro!r}") from None
                    self._dormir(self._espera(falhas, None))
        assert primeira is not None
        return Download(
            url_final=str(primeira.url),
            status=primeira.status_code,
            last_modified=primeira.headers.get("last-modified"),
            etag=primeira.headers.get("etag"),
            bytes=recebido,
            sha256=resumo.hexdigest(),
        )

    def listar_webdav(self, url: str, usuario: str) -> list[ItemWebdav]:
        """Conteúdo de uma pasta WebDAV (PROPFIND com profundidade 1), sem a própria pasta."""

        def tentativa() -> list[ItemWebdav]:
            resposta = self._cliente.request(
                "PROPFIND", url, headers={"Depth": "1"}, auth=(usuario, "")
            )
            self._verificar(resposta)
            return _itens_webdav(resposta.content, httpx.URL(url).path)

        return self._com_retentativas(url, tentativa)

    def obter_json(self, url: str, params: dict[str, Any] | None = None) -> RespostaJson:
        def tentativa() -> RespostaJson:
            resposta = self._cliente.get(url, params=params, headers={"Accept": "application/json"})
            self._verificar(resposta)
            dados = resposta.json() if resposta.content else None  # 204 No Content: sem registros
            return RespostaJson(str(resposta.url), resposta.status_code, resposta.content, dados)

        return self._com_retentativas(url, tentativa)

    def pausar(self, segundos: float) -> None:
        """Pausa entre requisições (usa o `dormir` injetado, instantâneo nos testes)."""
        if segundos > 0:
            self._dormir(segundos)

    def obter_texto(self, url: str) -> str:
        def tentativa() -> str:
            resposta = self._cliente.get(url)
            self._verificar(resposta)
            return resposta.text

        return self._com_retentativas(url, tentativa)

    @staticmethod
    def _verificar(resposta: httpx.Response) -> None:
        if resposta.status_code >= 400:
            raise _RespostaComErro(resposta)

    def _verificar_host(self, requisicao: httpx.Request) -> None:
        if self.sufixos_permitidos is None:
            return
        host = requisicao.url.host
        if not host_permitido(host, self.sufixos_permitidos):
            raise ErroHttp(str(requisicao.url), None, f"host não permitido: {host}")

    def _com_retentativas(self, url: str, tentativa: Callable[[], T]) -> T:
        ultimo: ErroHttp | None = None
        for numero in range(1, self._tentativas + 1):
            try:
                return tentativa()
            except _RespostaComErro as erro:
                status = erro.resposta.status_code
                ultimo = ErroHttp(str(erro.resposta.url), status, "resposta HTTP de erro")
                if status not in STATUS_RETENTAVEIS:
                    raise ultimo from None
                espera = self._espera(numero, erro.resposta.headers.get("retry-after"))
            except httpx.TransportError as erro:
                ultimo = ErroHttp(url, None, f"falha de transporte: {erro!r}")
                espera = self._espera(numero, None)
            if numero < self._tentativas:
                self._dormir(espera)
        assert ultimo is not None
        raise ultimo

    def _espera(self, numero: int, retry_after: str | None) -> float:
        if retry_after:
            try:
                return min(max(float(retry_after), 0.0), self._espera_maxima)
            except ValueError:
                try:
                    alvo = parsedate_to_datetime(retry_after)
                    segundos = (alvo - datetime.now(alvo.tzinfo)).total_seconds()
                    return min(max(segundos, 0.0), self._espera_maxima)
                except (TypeError, ValueError):
                    pass
        base = min(self._espera_base * 2 ** (numero - 1), self._espera_maxima)
        return base * random.uniform(0.5, 1.0)


def _itens_webdav(corpo: bytes, caminho_pasta: str) -> list[ItemWebdav]:
    dav = "{DAV:}"
    itens = []
    for resposta in ET.fromstring(corpo).iter(f"{dav}response"):
        href = unquote(resposta.findtext(f"{dav}href") or "")
        if href.rstrip("/") == caminho_pasta.rstrip("/"):
            continue
        pasta = resposta.find(f".//{dav}resourcetype/{dav}collection") is not None
        tamanho = resposta.findtext(f".//{dav}getcontentlength")
        nome = href.rstrip("/").rsplit("/", 1)[-1]
        itens.append(ItemWebdav(nome, pasta, int(tamanho) if tamanho else None))
    return itens
