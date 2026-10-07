"""Adaptador `api_detalhe`: lista os ids numa API JSON e busca o detalhe de cada um.

A lista usa as regras do `api_json` (paginação e iteração por legislatura); o detalhe de cada id
vem de `url_detalhe` (com `{id}`). As páginas de detalhe são gravadas no mesmo formato do
`api_json`, que também faz a preparação.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from datetime import date
from pathlib import Path

from coletor.adaptadores import api_json
from coletor.adaptadores.base import ErroColeta, Extracao, Preparado
from coletor.competencias import Competencia
from coletor.http import ClienteHttp
from coletor.manifesto import Recurso


def extrair(
    recurso: Recurso, competencia: Competencia | None, pasta: Path, http: ClienteHttp, hoje: date
) -> Extracao:
    assert recurso.url_detalhe is not None
    pasta_lista = pasta / "lista"
    pasta_lista.mkdir()
    lista = api_json.extrair(recurso, competencia, pasta_lista, http, hoje)
    itens = api_json.preparar(recurso, lista.competencia, lista.arquivo_original, pasta_lista)
    ids = sorted({str(item["id"]) for item in itens.registros or [] if isinstance(item, dict)})
    if not ids:
        raise ErroColeta(f"{recurso.id}: a lista não trouxe nenhum id")
    original = pasta / "paginas.jsonl.gz"
    resumo = hashlib.sha256()
    total = status = 0
    with gzip.open(original, "wt", encoding="utf-8") as saida:
        for indice, id_ in enumerate(ids):
            if indice:
                http.pausar(recurso.pausa_pagina_segundos)
            resposta = http.obter_json(recurso.url_detalhe.replace("{id}", id_))
            pagina = {
                "url": resposta.url_final,
                "status": resposta.status,
                "corpo": resposta.corpo.decode("utf-8") or "null",
            }
            saida.write(json.dumps(pagina, ensure_ascii=False) + "\n")
            resumo.update(resposta.corpo)
            total += len(resposta.corpo)
            status = resposta.status
    return Extracao(
        competencia=lista.competencia,
        arquivo_original=original,
        extensao="jsonl.gz",
        url=recurso.url_detalhe,
        http_status=status,
        bytes_arquivo=total,
        sha256_arquivo=resumo.hexdigest(),
        parametros={**lista.parametros, "ids": len(ids)},
    )


def preparar(recurso: Recurso, competencia: Competencia, original: Path, pasta: Path) -> Preparado:
    return api_json.preparar(recurso, competencia, original, pasta)
