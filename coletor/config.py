"""Configuração do coletor, lida de variáveis de ambiente."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

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
    lago: Path = Path("dados")
    publico: Path = Path("dados/publico")
    prefixo: str = ""

    @property
    def prefixo_gcs(self) -> str:
        """`ELEITORADO_PREFIXO` (`paralelo/` durante a migração) e, em dev, `dev/`."""
        return self.prefixo + ("dev/" if self.ambiente == "dev" else "")


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
    prefixo = env.get("ELEITORADO_PREFIXO", "")
    if prefixo and not prefixo.endswith("/"):
        raise ErroConfig(f"ELEITORADO_PREFIXO deve terminar com /, recebido: {prefixo!r}")
    return Config(
        projeto=env["ELEITORADO_PROJETO"],
        bucket=env["ELEITORADO_BUCKET"],
        regiao=env.get("ELEITORADO_REGIAO", "southamerica-east1"),
        ambiente=ambiente,
        versao=env.get("ELEITORADO_VERSAO", "local"),
        origem=origem,
        lago=Path(env.get("ELEITORADO_LAGO", "dados")),
        publico=Path(env.get("ELEITORADO_PUBLICO", "dados/publico")),
        prefixo=prefixo,
    )
