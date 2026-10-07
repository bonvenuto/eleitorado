"""Arquivos do site público (`coletor site`): lê `site_arquivos` do DuckDB, valida e grava em gzip.

Spec: docs/superpowers/specs/2026-10-07-site-publico-design.md, seções 4 e 5. Cada arquivo é
conferido antes de qualquer gravação (caminho, tamanho, CPF completo nos textos e o JSON Schema
do seu tipo) e gravado numa pasta temporária, que só substitui `site/` no fim: se algo falha, o
site anterior fica como estava.
"""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

TIPOS = ("resumo", "busca-parlamentares", "busca-empresas", "parlamentar", "empresa", "alertas")


class ErroSite(Exception):
    """Arquivo do site inválido: nada é gravado."""


def tipo_do_caminho(caminho: str) -> str:
    if caminho == "resumo.json":
        return "resumo"
    if caminho == "busca/parlamentares.json":
        return "busca-parlamentares"
    for prefixo, tipo in (
        ("busca/empresas/", "busca-empresas"),
        ("parlamentar/", "parlamentar"),
        ("empresa/", "empresa"),
        ("alertas/", "alertas"),
    ):
        if caminho.startswith(prefixo):
            return tipo
    raise ErroSite(f"caminho sem tipo conhecido: {caminho}")


def carregar_validadores(pasta: Path) -> dict[str, Draft202012Validator]:
    """Um validador por tipo de arquivo, com `comum.schema.json` disponível para os `$ref`."""
    esquemas = {
        arquivo.name.removesuffix(".schema.json"): json.loads(arquivo.read_text(encoding="utf-8"))
        for arquivo in pasta.glob("*.schema.json")
    }
    faltando = sorted(set(TIPOS) - set(esquemas))
    if faltando:
        raise ErroSite(f"esquemas ausentes em {pasta}: {', '.join(faltando)}")
    registro = Registry().with_resources(
        (esquema["$id"], Resource.from_contents(esquema)) for esquema in esquemas.values()
    )
    return {tipo: Draft202012Validator(esquemas[tipo], registry=registro) for tipo in TIPOS}
