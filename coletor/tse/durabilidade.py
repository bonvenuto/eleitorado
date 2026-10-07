"""Documentos privados completos e sincronizados antes da instalação exclusiva."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from coletor.adaptadores.base import ErroColeta
from coletor.hashes import json_canonico


def sincronizar_pasta(pasta: Path) -> None:
    """Persiste entradas de diretório em POSIX; Windows usa arquivos fsync antes dos links."""
    if os.name != "nt":
        descritor = os.open(pasta, os.O_RDONLY)
        try:
            os.fsync(descritor)
        finally:
            os.close(descritor)


def gravar_json(destino: Path, dados: dict[str, Any], *, checksum: bool = False) -> None:
    """Instala documento por link exclusivo, sem expor JSON parcial ou sobrescrever."""
    conteudo = json_canonico(dados).encode("utf-8")
    if checksum:
        conteudo = json_canonico(
            {"sha256": hashlib.sha256(conteudo).hexdigest(), "dados": dados}
        ).encode("utf-8")
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = None
    try:
        with tempfile.NamedTemporaryFile(dir=destino.parent, delete=False) as saida:
            temporario = Path(saida.name)
            saida.write(conteudo)
            saida.flush()
            os.fsync(saida.fileno())
        os.link(temporario, destino)
        sincronizar_pasta(destino.parent)
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)


def ler_json_conferido(caminho: Path) -> dict[str, Any]:
    envelope = json.loads(caminho.read_text(encoding="utf-8"))
    dados = envelope["dados"]
    if hashlib.sha256(json_canonico(dados).encode("utf-8")).hexdigest() != envelope["sha256"]:
        raise ErroColeta("integridade do documento durável TSE divergente")
    return dados
