"""Configuração do agente (agente/config.toml)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO = Path(__file__).resolve().parent / "config.toml"


@dataclass(frozen=True)
class Orcamento:
    ciclos: int
    minutos: int
    hipoteses: int
    rodadas_validacao: int


@dataclass(frozen=True)
class ConfigAgente:
    raiz: Path
    lago: Path
    investigacoes: Path
    prefixo_gcs: str
    modelo: str | None
    tempo_consulta_s: int
    linhas_exibidas: int
    linhas_salvas: int
    livre: Orcamento
    tema: Orcamento

    @property
    def banco(self) -> Path:
        return self.lago / "agente.duckdb"

    @property
    def publico(self) -> Path:
        return self.lago / "publico"

    @property
    def caderno(self) -> Path:
        return self.investigacoes / "caderno"

    def diretorios_permitidos(self) -> list[Path]:
        """Diretórios que as views do banco leem: o raw, o meta e os marts."""
        return [self.lago / "raw", self.lago / "meta", self.publico]

    def orcamento(self, tema: str | None) -> Orcamento:
        return self.tema if tema else self.livre


def carregar(arquivo: Path = ARQUIVO, raiz: Path = RAIZ) -> ConfigAgente:
    dados = tomllib.loads(arquivo.read_text(encoding="utf-8"))
    caminhos = dados["caminhos"]
    consulta = dados["consulta"]
    return ConfigAgente(
        raiz=raiz,
        lago=(raiz / caminhos["lago"]).resolve(),
        investigacoes=(raiz / caminhos["investigacoes"]).resolve(),
        prefixo_gcs=dados["coleta"]["prefixo_gcs"],
        modelo=dados["modelo"]["nome"] or None,
        tempo_consulta_s=consulta["tempo_maximo_s"],
        linhas_exibidas=consulta["linhas_exibidas"],
        linhas_salvas=consulta["linhas_salvas"],
        livre=Orcamento(**dados["orcamento"]["livre"]),
        tema=Orcamento(**dados["orcamento"]["tema"]),
    )
