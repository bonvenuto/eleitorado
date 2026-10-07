"""Configuração do agente (agente/config.toml)."""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO = Path(__file__).resolve().parent / "config.toml"


FAMILIAS_TSE = (
    "bens",
    "candidaturas",
    "contratadas",
    "doador_originario",
    "pagamentos",
    "receitas",
)


def preparo_c2_pendente(lago: Path) -> bool:
    """Existência basta: conteúdo inválido ou link pendente também bloqueia."""
    caminho = lago / "preparo-c2-pendente.json"
    return caminho.exists() or caminho.is_symlink()


def _confinado_tse(lago: Path, relativo: str) -> Path:
    lago = lago.absolute()
    destino = lago / relativo
    atual = lago
    for parte in Path(relativo).parts:
        atual /= parte
        if atual.is_symlink() or atual.is_junction():
            raise ValueError("diretório TSE simbólico ou junction")
    if lago.resolve() != lago or destino.resolve() != destino:
        raise ValueError("diretório TSE fora do lago canônico")
    return destino


def saida_tse_permitida(lago: Path, execucao_id: str, declarada: str | None = None) -> Path:
    """Deriva somente a saída exata, nunca um caminho livre fornecido pela marca."""
    if not isinstance(execucao_id, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", execucao_id
    ):
        raise ValueError("execução TSE inválida na marca de preparo")
    saida = _confinado_tse(lago, f"estado/tse/publicacoes/preparadas/{execucao_id}/marts")
    if declarada is not None and (not isinstance(declarada, str) or Path(declarada) != saida):
        raise ValueError("saída TSE divergente na marca de preparo")
    return saida


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

    def diretorios_dados(self) -> list[Path]:
        """Base restrita para o preparo interno: fontes usuais e seis vazios fixos."""
        diretorios = [self.lago / "raw", self.lago / "meta", self.publico]
        diretorios += [
            _confinado_tse(self.lago, f"estado/tse/ci/{familia}/vazio") for familia in FAMILIAS_TSE
        ]
        return diretorios

    def diretorios_permitidos(self) -> list[Path]:
        """Leitura normal bloqueada durante tentativa C2 pendente."""
        if preparo_c2_pendente(self.lago):
            raise ValueError("preparo C2 pendente; reconstrua antes de consultar")
        diretorios = self.diretorios_dados()
        marca = self.lago / "preparo.json"
        if marca.exists():
            dados = json.loads(marca.read_bytes())
            if "tse" in dados:
                tse = dados["tse"]
                diretorios.append(
                    saida_tse_permitida(self.lago, tse["execucao_id"], tse.get("saida"))
                )
        return diretorios

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
