"""Publicação dos marts, da linhagem e do site no bucket público (Cloudflare R2, API do S3)."""

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

PERMITIDOS = ("marts/", "linhagem/", "site/")
SITE = "site/"
MANIFESTO = "manifesto.json"
TIPOS = {
    ".parquet": "application/vnd.apache.parquet",
    ".html": "text/html; charset=utf-8",
    ".json": "application/json",
}
# os JSON do site já estão em gzip (coletor site): o navegador descomprime pelo Content-Encoding
CACHE_SITE = "public, max-age=600"


class ErroPublicacao(Exception):
    """Arquivo fora de marts/, linhagem/ e site/: nada é publicado."""


class Publicador(Protocol):
    def listar(self) -> dict[str, str]:
        """Chave → ETag (o MD5 do conteúdo, sem aspas, em uploads sem multipart)."""
        ...

    def enviar(
        self,
        origem: Path,
        chave: str,
        tipo: str,
        codificacao: str | None = None,
        cache: str | None = None,
    ) -> None: ...

    def apagar(self, chave: str) -> None: ...


@dataclass(frozen=True)
class ResumoPublicacao:
    enviados: int
    apagados: int
    inalterados: int = 0


def _resumo(caminho: Path, algoritmo: str) -> str:
    resumo = hashlib.new(algoritmo)
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1 << 20), b""):
            resumo.update(bloco)
    return resumo.hexdigest()


def _sha256(caminho: Path) -> str:
    return _resumo(caminho, "sha256")


def _md5(caminho: Path) -> str:
    return _resumo(caminho, "md5")


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
    """Lista os dados para download (marts e linhagem); os arquivos do site ficam de fora."""
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
            if not chave.startswith(SITE)
        ],
    }


def publicar(
    publicador: Publicador, publico: Path, gerado_em: datetime, versao: str
) -> ResumoPublicacao:
    """Envia o que mudou, depois o manifesto, e só então apaga o que deixou de existir.

    Só envia o arquivo cujo MD5 difere do ETag no bucket. Sem `site/` local (o `coletor site`
    falhou ou não rodou), o `site/` do bucket fica como está, com os dados anteriores.
    """
    arquivos = arquivos_publicos(publico)
    anteriores = publicador.listar()
    enviados = 0
    for chave, caminho in sorted(arquivos.items()):
        if anteriores.get(chave) == _md5(caminho):
            continue
        tipo = TIPOS.get(caminho.suffix, "application/octet-stream")
        if chave.startswith(SITE):
            publicador.enviar(caminho, chave, tipo, codificacao="gzip", cache=CACHE_SITE)
        else:
            publicador.enviar(caminho, chave, tipo)
        enviados += 1
    manifesto = montar_manifesto(arquivos, gerado_em, versao)
    with tempfile.TemporaryDirectory() as pasta:
        destino = Path(pasta) / MANIFESTO
        destino.write_text(json.dumps(manifesto, ensure_ascii=False, indent=1), encoding="utf-8")
        publicador.enviar(destino, MANIFESTO, TIPOS[".json"])
    tem_site = any(chave.startswith(SITE) for chave in arquivos)
    sobrando = sorted(
        chave
        for chave in set(anteriores) - set(arquivos) - {MANIFESTO}
        if tem_site or not chave.startswith(SITE)
    )
    for chave in sobrando:
        publicador.apagar(chave)
    inalterados = len(arquivos) - enviados
    log.info(
        "publicados %d arquivo(s) (%d sem mudança); %d removido(s)",
        enviados,
        inalterados,
        len(sobrando),
    )
    return ResumoPublicacao(enviados + 1, len(sobrando), inalterados)


class R2Publicador:
    def __init__(self, conta: str, chave_id: str, segredo: str, bucket: str) -> None:
        import boto3
        from boto3.s3.transfer import TransferConfig

        self._bucket = bucket
        self._s3 = boto3.client(
            "s3",
            endpoint_url=f"https://{conta}.r2.cloudflarestorage.com",
            aws_access_key_id=chave_id,
            aws_secret_access_key=segredo,
            region_name="auto",
        )
        # upload sem multipart (até 4 GB): o ETag fica sendo o MD5, que o envio incremental compara
        self._transferencia = TransferConfig(multipart_threshold=4 * 1024**3)

    def listar(self) -> dict[str, str]:
        chaves: dict[str, str] = {}
        for pagina in self._s3.get_paginator("list_objects_v2").paginate(Bucket=self._bucket):
            for objeto in pagina.get("Contents", []):
                chaves[objeto["Key"]] = objeto["ETag"].strip('"')
        return chaves

    def enviar(
        self,
        origem: Path,
        chave: str,
        tipo: str,
        codificacao: str | None = None,
        cache: str | None = None,
    ) -> None:
        extras = {"ContentType": tipo}
        if codificacao:
            extras["ContentEncoding"] = codificacao
        if cache:
            extras["CacheControl"] = cache
        self._s3.upload_file(
            str(origem), self._bucket, chave, ExtraArgs=extras, Config=self._transferencia
        )

    def apagar(self, chave: str) -> None:
        self._s3.delete_object(Bucket=self._bucket, Key=chave)
