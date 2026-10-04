"""Adaptador `api_json`: APIs JSON com paginação por link e iteração por legislatura."""

from __future__ import annotations

import gzip
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import httpx

from coletor.adaptadores.base import ErroColeta, Extracao, Preparado, preencher
from coletor.competencias import Competencia, legislaturas
from coletor.hashes import sha256_registros
from coletor.http import ClienteHttp
from coletor.manifesto import Recurso

LIMITE_PAGINAS = 10_000


def chave_url(url: str) -> tuple[str, str, tuple[tuple[str, str], ...]]:
    """Identifica uma URL sem depender da ordem dos parâmetros."""
    endereco = httpx.URL(url)
    return endereco.host, endereco.path, tuple(sorted(endereco.params.multi_items()))


def proximo_link(dados: Any) -> str | None:
    if isinstance(dados, dict):
        for link in dados.get("links") or []:
            if isinstance(link, dict) and link.get("rel") == "next" and link.get("href"):
                return str(link["href"])
    return None


def extrair_registros(dados: Any, caminho: str | None) -> list[Any]:
    atual = dados
    if caminho:
        for parte in caminho.split("."):
            if not isinstance(atual, dict) or parte not in atual:
                raise ErroColeta(f"caminho '{caminho}' não encontrado (parou em '{parte}')")
            atual = atual[parte]
    if atual is None:
        return []
    if isinstance(atual, dict):
        return [atual]
    if isinstance(atual, list):
        return atual
    raise ErroColeta(f"registros em '{caminho}' não são lista nem objeto")


def extrair(
    recurso: Recurso, competencia: Competencia | None, pasta: Path, http: ClienteHttp, hoje: date
) -> Extracao:
    if competencia is None:
        raise ErroColeta(f"{recurso.id}: competência obrigatória")
    url_base = preencher(recurso.url, competencia, hoje)
    valores: list[int | None] = [None]
    if recurso.iteracao is not None:
        valores = list(legislaturas(recurso.iteracao.inicio, hoje))
    original = pasta / "paginas.jsonl.gz"
    resumo = hashlib.sha256()
    total = 0
    status = 0
    paginas = 0
    with gzip.open(original, "wt", encoding="utf-8") as saida:
        for valor in valores:
            params: dict[str, Any] | None = dict(recurso.parametros)
            if recurso.iteracao is not None:
                params[recurso.iteracao.parametro] = valor
            url: str | None = url_base
            visitadas: set[tuple[str, str, tuple[tuple[str, str], ...]]] = set()
            while url is not None:
                resposta = http.obter_json(url, params)
                paginas += 1
                if paginas > LIMITE_PAGINAS:
                    raise ErroColeta(f"mais de {LIMITE_PAGINAS} páginas: paginação em laço?")
                visitadas.add(chave_url(resposta.url_final))
                pagina = {
                    "url": resposta.url_final,
                    "status": resposta.status,
                    "corpo": resposta.corpo.decode("utf-8"),
                }
                saida.write(json.dumps(pagina, ensure_ascii=False) + "\n")
                resumo.update(resposta.corpo)
                total += len(resposta.corpo)
                status = resposta.status
                url, params = None, None
                if recurso.paginacao == "links_next":
                    seguinte = proximo_link(resposta.dados)
                    if seguinte is not None and chave_url(seguinte) not in visitadas:
                        url = seguinte
    parametros: dict[str, Any] = {"parametros": dict(recurso.parametros)}
    if recurso.iteracao is not None:
        parametros["iteracao"] = {"parametro": recurso.iteracao.parametro, "valores": valores}
    return Extracao(
        competencia=competencia,
        arquivo_original=original,
        extensao="jsonl.gz",
        url=url_base,
        http_status=status,
        bytes_arquivo=total,
        sha256_arquivo=resumo.hexdigest(),
        parametros=parametros,
    )


def preparar(recurso: Recurso, competencia: Competencia, original: Path, pasta: Path) -> Preparado:
    registros: list[Any] = []
    with gzip.open(original, "rt", encoding="utf-8") as entrada:
        for linha in entrada:
            pagina = json.loads(linha)
            registros.extend(extrair_registros(json.loads(pagina["corpo"]), recurso.registros))
    return Preparado(sha256_conteudo=sha256_registros(registros), registros=registros)
