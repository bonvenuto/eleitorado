"""Hashes SHA-256 de arquivos e de registros JSON."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

_BLOCO = 1 << 20


def sha256_arquivo(caminho: Path) -> str:
    resumo = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(_BLOCO), b""):
            resumo.update(bloco)
    return resumo.hexdigest()


def json_canonico(registro: Any) -> str:
    return json.dumps(registro, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_registros(registros: Iterable[Any]) -> str:
    """Hash independente da ordem dos registros e da ordem das chaves."""
    resumo = hashlib.sha256()
    for linha in sorted(json_canonico(registro) for registro in registros):
        resumo.update(linha.encode("utf-8"))
        resumo.update(b"\n")
    return resumo.hexdigest()
