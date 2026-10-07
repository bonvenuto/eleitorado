"""Adaptadores de coleta, escolhidos pelo campo `adaptador` do manifesto.

Cada módulo expõe `extrair(recurso, competencia, pasta, http, hoje) -> Extracao`
e `preparar(recurso, competencia, original, pasta) -> Preparado`.
"""

from __future__ import annotations

from types import ModuleType

from coletor.adaptadores import api_detalhe, api_json, arquivo, webdav_zip
from coletor.manifesto import Recurso

ADAPTADORES: dict[str, ModuleType] = {
    "arquivo": arquivo,
    "api_json": api_json,
    "webdav_zip": webdav_zip,
    "api_detalhe": api_detalhe,
}


def adaptador_para(recurso: Recurso) -> ModuleType:
    return ADAPTADORES[recurso.adaptador]
