"""Hook PreToolUse do Claude Code para WebSearch e WebFetch: nenhum CPF sai da máquina.

Recebe o evento em JSON pela entrada padrão; sai com código 2 (bloqueia) quando a entrada da
ferramenta tem uma sequência de 11 dígitos, com ou sem pontuação. CNPJ (14 dígitos) passa.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any, TextIO

PADRAO_CPF = re.compile(r"(?<!\d)\d{3}[.\s]?\d{3}[.\s]?\d{3}[-\s]?\d{2}(?!\d)")


def motivo_bloqueio(evento: dict[str, Any]) -> str | None:
    texto = json.dumps(evento.get("tool_input", {}), ensure_ascii=False)
    if PADRAO_CPF.search(texto):
        return (
            "bloqueado: a busca contém uma sequência de 11 dígitos (possível CPF ou número de "
            "processo). Pesquise por nome, CNPJ ou outra referência."
        )
    return None


def main(entrada: TextIO = sys.stdin, erro: TextIO = sys.stderr) -> int:
    try:
        evento = json.load(entrada)
    except json.JSONDecodeError:
        print("bloqueado: evento do hook ilegível", file=erro)
        return 2
    motivo = motivo_bloqueio(evento)
    if motivo:
        print(motivo, file=erro)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
