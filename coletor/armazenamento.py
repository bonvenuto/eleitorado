"""Gravação de originais e arquivos de carga no Cloud Storage."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Protocol


class Armazenamento(Protocol):
    def enviar(self, origem: Path, caminho: str) -> str:
        """Grava sem sobrescrever e devolve a URI `gs://`.

        Os caminhos incluem o hash do conteúdo ou o id da coleta: se o objeto já
        existe, ele tem o mesmo conteúdo e é reaproveitado.
        """
        ...

    def baixar(self, caminho: str, destino: Path) -> None: ...

    def listar(self, prefixo: str) -> list[str]: ...


def caminho_original(
    prefixo: str,
    orgao: str,
    recurso: str,
    competencia: str,
    instante: datetime,
    sha256_conteudo: str,
    extensao: str,
) -> str:
    return (
        f"{prefixo}originais/{orgao}/{recurso}/competencia={competencia}/"
        f"{instante:%Y%m%dT%H%M%S}_{sha256_conteudo[:12]}.{extensao}"
    )


def caminho_carga(prefixo: str, orgao: str, recurso: str, competencia: str, coleta_id: str) -> str:
    return f"{prefixo}carga/{orgao}/{recurso}/competencia={competencia}/{coleta_id}.parquet"


def caminho_de_uri(uri: str) -> str:
    """`gs://bucket/a/b.zip` vira `a/b.zip`."""
    if not uri.startswith("gs://"):
        raise ValueError(f"URI do GCS inválida: {uri}")
    return uri.removeprefix("gs://").split("/", 1)[1]


class GcsArmazenamento:
    def __init__(self, bucket: str, projeto: str, credenciais: Any = None) -> None:
        from google.cloud import storage

        self._cliente = storage.Client(project=projeto, credentials=credenciais)
        self._bucket = self._cliente.bucket(bucket)
        self._nome = bucket

    def enviar(self, origem: Path, caminho: str) -> str:
        from google.api_core.exceptions import PreconditionFailed

        try:
            self._bucket.blob(caminho).upload_from_filename(str(origem), if_generation_match=0)
        except PreconditionFailed:
            pass  # já existe com o mesmo conteúdo (caminho endereçado por conteúdo)
        return f"gs://{self._nome}/{caminho}"

    def baixar(self, caminho: str, destino: Path) -> None:
        self._bucket.blob(caminho).download_to_filename(str(destino))

    def listar(self, prefixo: str) -> list[str]:
        return sorted(blob.name for blob in self._cliente.list_blobs(self._bucket, prefix=prefixo))
