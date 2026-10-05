"""Tipos comuns aos adaptadores de coleta."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

from coletor.competencias import Competencia, legislatura_atual


class ErroColeta(Exception):
    """Falha de coleta com mensagem destinada a `meta.coletas`."""


@dataclass(frozen=True)
class Extracao:
    """O que foi baixado da fonte, antes de qualquer transformação."""

    competencia: Competencia
    arquivo_original: Path
    extensao: str
    url: str
    http_status: int
    bytes_arquivo: int
    sha256_arquivo: str
    last_modified: str | None = None
    etag: str | None = None
    parametros: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Preparado:
    """Conteúdo pronto para conversão: um CSV ou uma lista de registros."""

    sha256_conteudo: str
    csv: Path | None = None
    registros: list[Any] | None = None


def preencher(modelo: str, competencia: Competencia | None, dia: date) -> str:
    """Substitui `{ano}`, `{mes}`, `{anomes}`, `{data}`, `{legislatura}`, `{ontem}` e
    `{semana_passada}` em URLs e nomes de arquivo.
    """
    valores: dict[str, Any] = {"legislatura": legislatura_atual(dia)}
    valores["ontem"] = (dia - timedelta(days=1)).strftime("%Y%m%d")
    valores["semana_passada"] = (dia - timedelta(days=7)).strftime("%Y%m%d")
    if competencia is not None:
        valores["ano"] = competencia.data.year
        valores["anomes"] = competencia.data.strftime("%Y%m")
        valores["mes"] = competencia.data.strftime("%m")
        valores["data"] = competencia.data.strftime("%Y%m%d")

    try:
        return modelo.format_map(valores)
    except KeyError as erro:
        raise ErroColeta(f"marcador sem valor em {modelo!r}: {erro}") from None


def extensao_de(url: str) -> str:
    nome = PurePosixPath(urlparse(url).path).name
    return nome.split(".", 1)[1].lower() if "." in nome else "bin"
