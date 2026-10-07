"""Arquivos do site público (`coletor site`): lê `site_arquivos` do DuckDB, valida e grava em gzip.

Spec: docs/superpowers/specs/2026-10-07-site-publico-design.md, seções 4 e 5. Cada arquivo é
conferido antes de qualquer gravação (caminho, tamanho, CPF completo nos textos e o JSON Schema
do seu tipo) e gravado numa pasta temporária, que só substitui `site/` no fim: se algo falha, o
site anterior fica como estava.
"""

from __future__ import annotations

import gzip
import json
import re
import shutil
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

TIPOS = ("resumo", "busca-parlamentares", "busca-empresas", "parlamentar", "empresa", "alertas")
OBRIGATORIOS = ("resumo", "busca-parlamentares")
LIMITE_DESCOMPRIMIDO = 2_000_000
LIMITE_GZIP = 500_000
# os blocos de empresa e de busca de empresa são milhares: o esquema é conferido numa amostra
AMOSTRADOS = ("empresa", "busca-empresas")
AMOSTRA = 20
CAMINHO = re.compile(r"^[A-Za-z0-9_-]+(/[A-Za-z0-9_-]+)*\.json$")
# o mesmo padrão do teste `sem_cpf_completo` do dbt
CPF = re.compile(r"(^|[^0-9])[0-9]{3}\.?[0-9]{3}\.?[0-9]{3}-?[0-9]{2}([^0-9]|$)")


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


def _textos(valor: Any) -> Iterator[str]:
    """Os textos do JSON, menos os das chaves `*_id` (como o teste `sem_cpf_completo` do dbt:
    um MD5 pode começar com 11 dígitos)."""
    if isinstance(valor, str):
        yield valor
    elif isinstance(valor, dict):
        for chave, item in valor.items():
            if not chave.endswith("_id"):
                yield from _textos(item)
    elif isinstance(valor, list):
        for item in valor:
            yield from _textos(item)


def _conferir(
    caminho: str,
    conteudo: str,
    validador: Draft202012Validator | None,
    limite_descomprimido: int,
    limite_gzip: int,
) -> bytes:
    """Confere um arquivo e devolve o conteúdo em gzip (determinístico: `mtime=0`)."""
    if not CAMINHO.match(caminho):
        raise ErroSite(f"caminho inválido: {caminho!r}")
    dados = conteudo.encode("utf-8")
    if len(dados) > limite_descomprimido:
        raise ErroSite(f"{caminho}: {len(dados)} bytes (limite {limite_descomprimido})")
    comprimido = gzip.compress(dados, compresslevel=9, mtime=0)
    if len(comprimido) > limite_gzip:
        raise ErroSite(f"{caminho}: {len(comprimido)} bytes em gzip (limite {limite_gzip})")
    documento = json.loads(conteudo)
    # a mensagem não traz o texto: o log do Actions é público
    if any(CPF.search(texto) for texto in _textos(documento)):
        raise ErroSite(f"{caminho}: CPF completo num texto")
    if validador is not None:
        erro = next(iter(sorted(validador.iter_errors(documento), key=lambda e: e.json_path)), None)
        if erro is not None:
            raise ErroSite(f"{caminho}: fora do esquema em {erro.json_path}: {erro.message}")
    return comprimido


def _trocar(novo: Path, destino: Path) -> None:
    """Põe `novo` no lugar de `destino`. No Windows, a pasta recém-apagada às vezes fica presa por
    um instante (antivírus, indexador): tenta de novo algumas vezes."""
    if destino.exists():
        shutil.rmtree(destino)
    for tentativa in range(5):
        try:
            novo.rename(destino)
            return
        except PermissionError:
            if tentativa == 4:
                raise
            time.sleep(0.2 * (tentativa + 1))


def gerar_site(
    banco: Path,
    publico: Path,
    esquemas: Path,
    *,
    limite_descomprimido: int = LIMITE_DESCOMPRIMIDO,
    limite_gzip: int = LIMITE_GZIP,
) -> int:
    """Grava `publico/site/<caminho>` (JSON em gzip) a partir de `site.site_arquivos` do banco."""
    import duckdb

    validadores = carregar_validadores(esquemas)
    if not banco.exists():
        raise ErroSite(f"{banco} não existe: rode o dbt antes")
    destino = publico / "site"
    novo = publico / "site.novo"
    if novo.exists():
        shutil.rmtree(novo)
    vistos: dict[str, int] = {}
    con = duckdb.connect(str(banco), read_only=True)
    try:
        cursor = con.execute("select caminho, conteudo from site.site_arquivos order by caminho")
        while lote := cursor.fetchmany(500):
            for caminho, conteudo in lote:
                tipo = tipo_do_caminho(caminho)
                vistos[tipo] = vistos.get(tipo, 0) + 1
                amostrado = tipo in AMOSTRADOS and vistos[tipo] > AMOSTRA
                comprimido = _conferir(
                    caminho,
                    conteudo,
                    None if amostrado else validadores[tipo],
                    limite_descomprimido,
                    limite_gzip,
                )
                arquivo = novo / caminho
                arquivo.parent.mkdir(parents=True, exist_ok=True)
                arquivo.write_bytes(comprimido)
        faltando = [tipo for tipo in OBRIGATORIOS if tipo not in vistos]
        if faltando:
            raise ErroSite(f"sem arquivo de {', '.join(faltando)}")
    except BaseException:
        shutil.rmtree(novo, ignore_errors=True)
        raise
    finally:
        con.close()
    _trocar(novo, destino)
    return sum(vistos.values())
