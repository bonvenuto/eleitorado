"""Publicação dos marts e da linhagem no bucket público (Cloudflare R2, API do S3)."""

from __future__ import annotations

import hashlib
import json
import logging
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

log = logging.getLogger(__name__)

PERMITIDOS = ("marts/", "linhagem/")
MANIFESTO = "manifesto.json"
TIPOS = {
    ".parquet": "application/vnd.apache.parquet",
    ".html": "text/html; charset=utf-8",
    ".json": "application/json",
}


class ErroPublicacao(Exception):
    """Arquivo fora de marts/ e linhagem/: nada é publicado."""


class Publicador(Protocol):
    def listar(self) -> set[str]: ...

    def enviar(self, origem: Path, chave: str, tipo: str) -> None: ...

    def apagar(self, chave: str) -> None: ...


@dataclass(frozen=True)
class ResumoPublicacao:
    enviados: int
    apagados: int


def _sha256(caminho: Path) -> str:
    resumo = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1 << 20), b""):
            resumo.update(bloco)
    return resumo.hexdigest()


def _linhas(caminho: Path) -> int | None:
    if caminho.suffix != ".parquet":
        return None
    import pyarrow.parquet as pq

    return pq.ParquetFile(caminho).metadata.num_rows


def arquivos_publicos(publico: Path) -> dict[str, Path]:
    arquivos = {
        caminho.relative_to(publico).as_posix(): caminho
        for caminho in publico.rglob("*")
        if caminho.is_file()
    }
    proibidos = sorted(chave for chave in arquivos if not chave.startswith(PERMITIDOS))
    if proibidos:
        raise ErroPublicacao(f"fora de {', '.join(PERMITIDOS)}: {', '.join(proibidos)}")
    if not any(chave.startswith("marts/") for chave in arquivos):
        raise ErroPublicacao(f"nenhum mart em {publico}/marts")
    return arquivos


def montar_manifesto(
    arquivos: Mapping[str, Path], gerado_em: datetime, versao: str
) -> dict[str, Any]:
    return {
        "gerado_em": gerado_em.isoformat(),
        "versao": versao,
        "arquivos": [
            {
                "caminho": chave,
                "bytes": caminho.stat().st_size,
                "linhas": _linhas(caminho),
                "sha256": _sha256(caminho),
            }
            for chave, caminho in sorted(arquivos.items())
        ],
    }


def publicar(
    publicador: Publicador, publico: Path, gerado_em: datetime, versao: str
) -> ResumoPublicacao:
    """Envia os arquivos, depois o manifesto, e só então apaga o que deixou de existir."""
    arquivos = arquivos_publicos(publico)
    anteriores = publicador.listar()
    for chave, caminho in sorted(arquivos.items()):
        publicador.enviar(caminho, chave, TIPOS.get(caminho.suffix, "application/octet-stream"))
    manifesto = montar_manifesto(arquivos, gerado_em, versao)
    with tempfile.TemporaryDirectory() as pasta:
        destino = Path(pasta) / MANIFESTO
        destino.write_text(json.dumps(manifesto, ensure_ascii=False, indent=1), encoding="utf-8")
        publicador.enviar(destino, MANIFESTO, TIPOS[".json"])
    sobrando = sorted(anteriores - set(arquivos) - {MANIFESTO})
    for chave in sobrando:
        publicador.apagar(chave)
    log.info("publicados %d arquivo(s); %d removido(s)", len(arquivos), len(sobrando))
    return ResumoPublicacao(len(arquivos) + 1, len(sobrando))


class R2Publicador:
    def __init__(self, conta: str, chave_id: str, segredo: str, bucket: str) -> None:
        import boto3

        self._bucket = bucket
        self._s3 = boto3.client(
            "s3",
            endpoint_url=f"https://{conta}.r2.cloudflarestorage.com",
            aws_access_key_id=chave_id,
            aws_secret_access_key=segredo,
            region_name="auto",
        )

    def listar(self) -> set[str]:
        chaves: set[str] = set()
        for pagina in self._s3.get_paginator("list_objects_v2").paginate(Bucket=self._bucket):
            chaves.update(objeto["Key"] for objeto in pagina.get("Contents", []))
        return chaves

    def enviar(self, origem: Path, chave: str, tipo: str) -> None:
        self._s3.upload_file(str(origem), self._bucket, chave, ExtraArgs={"ContentType": tipo})

    def apagar(self, chave: str) -> None:
        self._s3.delete_object(Bucket=self._bucket, Key=chave)
