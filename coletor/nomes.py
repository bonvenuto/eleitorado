"""Normalização dos nomes de coluna gravados no raw."""

from __future__ import annotations

import re
import unicodedata

_NAO_ALFANUMERICO = re.compile(r"[^a-z0-9]+")


def normalizar_nome_coluna(nome: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    normalizado = _NAO_ALFANUMERICO.sub("_", sem_acento.lower()).strip("_")
    if not normalizado:
        return "coluna"
    if normalizado[0].isdigit():
        return f"c_{normalizado}"
    return normalizado


def normalizar_cabecalho(nomes: list[str]) -> tuple[list[str], list[list[str]]]:
    """Normaliza os nomes e desfaz colisões com sufixos `_2`, `_3`...

    Retorna os nomes normalizados e os pares `[original, normalizado]`.
    """
    vistos: set[str] = set()
    normalizados: list[str] = []
    for nome in nomes:
        base = normalizar_nome_coluna(nome)
        final, numero = base, 1
        while final in vistos:
            numero += 1
            final = f"{base}_{numero}"
        vistos.add(final)
        normalizados.append(final)
    return normalizados, [[o, n] for o, n in zip(nomes, normalizados, strict=True)]
