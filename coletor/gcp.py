"""Montagem das dependências reais (GCP e HTTP)."""

from __future__ import annotations

from datetime import UTC, datetime

from coletor.armazenamento import GcsArmazenamento
from coletor.coleta import Dependencias
from coletor.config import Config
from coletor.http import ClienteHttp
from coletor.warehouse import BigQueryWarehouse


def agora_utc() -> datetime:
    return datetime.now(UTC)


def montar_dependencias(config: Config) -> Dependencias:
    import google.auth

    credenciais, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
        quota_project_id=config.projeto,
    )
    return Dependencias(
        config=config,
        http=ClienteHttp(),
        armazenamento=GcsArmazenamento(config.bucket, config.projeto, credenciais),
        warehouse=BigQueryWarehouse(config.projeto, config.regiao, credenciais),
        agora=agora_utc,
    )
