"""Configuração do coletor, lida de variáveis de ambiente."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

AMBIENTES = ("dev", "prod")


class ErroConfig(Exception):
    """Configuração ausente ou inválida."""


@dataclass(frozen=True)
class Config:
    projeto: str
    bucket: str
    regiao: str
    ambiente: str
    versao: str
    origem: str

    @property
    def prefixo_gcs(self) -> str:
        return "dev/" if self.ambiente == "dev" else ""

    def dataset(self, nome: str) -> str:
        """Nome do dataset no ambiente: `raw_cgu` vira `raw_cgu_dev` em dev."""
        return f"{nome}_dev" if self.ambiente == "dev" else nome


def carregar_config(env: Mapping[str, str] | None = None) -> Config:
    env = os.environ if env is None else env
    faltando = [nome for nome in ("ELEITORADO_PROJETO", "ELEITORADO_BUCKET") if not env.get(nome)]
    if faltando:
        raise ErroConfig(f"variáveis de ambiente ausentes: {', '.join(faltando)}")
    ambiente = env.get("ELEITORADO_AMBIENTE", "dev")
    if ambiente not in AMBIENTES:
        raise ErroConfig(f"ELEITORADO_AMBIENTE deve ser dev ou prod, recebido: {ambiente!r}")
    origem = env.get("ELEITORADO_ORIGEM", "manual")
    if origem not in ("manual", "agendada"):
        raise ErroConfig(f"ELEITORADO_ORIGEM deve ser manual ou agendada, recebido: {origem!r}")
    return Config(
        projeto=env["ELEITORADO_PROJETO"],
        bucket=env["ELEITORADO_BUCKET"],
        regiao=env.get("ELEITORADO_REGIAO", "southamerica-east1"),
        ambiente=ambiente,
        versao=env.get("ELEITORADO_VERSAO", "local"),
        origem=origem,
    )
