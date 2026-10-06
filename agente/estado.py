"""Persistência do estado de uma investigação (investigacoes/<id>/estado.json).

Durante uma sessão do Claude, o estado é do servidor MCP (que registra hipóteses e achados);
entre sessões, é do controlador. A escrita é atômica: um arquivo temporário substitui o anterior.
"""

from __future__ import annotations

import os
from pathlib import Path

from agente.modelos import Estado

ARQUIVO = "estado.json"


def salvar(pasta: Path, estado: Estado) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    temporario = pasta / (ARQUIVO + ".tmp")
    temporario.write_text(estado.model_dump_json(indent=1), encoding="utf-8")
    os.replace(temporario, pasta / ARQUIVO)


def carregar(pasta: Path) -> Estado:
    return Estado.model_validate_json((pasta / ARQUIVO).read_text(encoding="utf-8"))


def existe(pasta: Path) -> bool:
    return (pasta / ARQUIVO).exists()
