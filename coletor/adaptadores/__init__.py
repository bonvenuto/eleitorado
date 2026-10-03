"""Adaptadores de coleta, escolhidos pelo campo `adaptador` do manifesto.

Cada módulo expõe `extrair(recurso, competencia, pasta, http, hoje) -> Extracao`
e `preparar(recurso, competencia, original, pasta) -> Preparado`.
"""

from __future__ import annotations

from types import ModuleType

from coletor.adaptadores import api_json, arquivo
from coletor.manifesto import Recurso

ADAPTADORES: dict[str, ModuleType] = {"arquivo": arquivo, "api_json": api_json}


def adaptador_para(recurso: Recurso) -> ModuleType:
    return ADAPTADORES[recurso.adaptador]
