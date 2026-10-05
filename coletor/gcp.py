"""Montagem das dependências reais: GCS, lago local e HTTP."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from coletor.armazenamento import GcsArmazenamento
from coletor.coleta import Dependencias
from coletor.config import Config
from coletor.http import ClienteHttp
from coletor.lago import LagoWarehouse


def agora_utc() -> datetime:
    return datetime.now(UTC)


def credenciais_do_ambiente(projeto: str, obter: Callable[..., Any] | None = None) -> Any:
    """Credenciais do ADC; só as de usuário recebem o projeto como quota project.

    No computador local, o ADC do usuário pode carregar o quota project de outro projeto.
    No GitHub (WIF), forçar o quota project exigiria serviceusage.services.use até da
    identidade federada, então ele não é aplicado.
    """
    import google.auth
    import google.oauth2.credentials

    obter = obter or google.auth.default
    credenciais, _ = obter(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    if isinstance(credenciais, google.oauth2.credentials.Credentials):
        return credenciais.with_quota_project(projeto)
    return credenciais


def montar_dependencias(config: Config) -> Dependencias:
    credenciais = credenciais_do_ambiente(config.projeto)
    return Dependencias(
        config=config,
        http=ClienteHttp(),
        armazenamento=GcsArmazenamento(config.bucket, config.projeto, credenciais),
        warehouse=LagoWarehouse(config.lago),
        agora=agora_utc,
    )
