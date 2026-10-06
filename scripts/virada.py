"""Virada do paralelo (Plano 5): copia `paralelo/<pasta>/` para `<pasta>/` no bucket privado.

Cópia no servidor (rewrite), sem sobrescrever: um objeto que já existe no destino é mantido e
contado. Pastas: originais, raw, meta e estado. Uso, com as credenciais do .env:

    uv run python scripts/virada.py conferir   # só lista o que falta copiar (não altera nada)
    uv run python scripts/virada.py copiar     # copia o que falta e confere no fim
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field

ORIGEM = "paralelo/"
PASTAS = ("originais/", "raw/", "meta/", "estado/")
BUCKET = "dados-publicos-prd-dados"


@dataclass
class Plano:
    copiar: list[tuple[str, str]] = field(default_factory=list)  # (origem, destino)
    ja_existem: list[str] = field(default_factory=list)
    divergentes: list[str] = field(default_factory=list)  # existe no destino com outro tamanho


def planejar(objetos: dict[str, int]) -> Plano:
    """`objetos`: nome -> tamanho de todo o bucket. Decide o que copiar para a raiz."""
    plano = Plano()
    for nome, tamanho in sorted(objetos.items()):
        if not nome.startswith(tuple(ORIGEM + p for p in PASTAS)):
            continue
        destino = nome.removeprefix(ORIGEM)
        if destino not in objetos:
            plano.copiar.append((nome, destino))
        elif objetos[destino] == tamanho:
            plano.ja_existem.append(destino)
        else:
            plano.divergentes.append(destino)
    return plano


def conferir_copia(objetos: dict[str, int]) -> list[str]:
    """Objetos de `paralelo/` sem cópia de mesmo tamanho na raiz (vazio = virada completa)."""
    plano = planejar(objetos)
    return [origem for origem, _ in plano.copiar] + plano.divergentes


def _objetos(bucket) -> dict[str, int]:
    return {blob.name: blob.size for blob in bucket.list_blobs()}


def _copiar(bucket, origem: str, destino: str) -> None:
    fonte = bucket.blob(origem)
    alvo = bucket.blob(destino)
    token, _, _ = alvo.rewrite(fonte, if_generation_match=0)
    while token is not None:  # objetos grandes precisam de várias chamadas
        token, _, _ = alvo.rewrite(fonte, token=token, if_generation_match=0)


def main(argv: list[str]) -> int:
    from google.cloud import storage

    if argv not in (["conferir"], ["copiar"]):
        print(__doc__)
        return 2
    bucket = storage.Client(project=BUCKET.removesuffix("-dados")).bucket(BUCKET)
    plano = planejar(_objetos(bucket))
    print(
        f"a copiar: {len(plano.copiar)}; já na raiz: {len(plano.ja_existem)}; "
        f"divergentes: {len(plano.divergentes)}"
    )
    for nome in plano.divergentes:
        print(f"  DIVERGENTE (mesmo nome, outro tamanho; não é tocado): {nome}")
    if argv == ["conferir"]:
        return 0 if not plano.divergentes else 1
    for indice, (origem, destino) in enumerate(plano.copiar, start=1):
        _copiar(bucket, origem, destino)
        if indice % 50 == 0:
            print(f"  {indice}/{len(plano.copiar)} copiados")
    faltando = conferir_copia(_objetos(bucket))
    print(f"conferência: {len(faltando)} objeto(s) de paralelo/ sem cópia idêntica na raiz")
    return 0 if not faltando else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
