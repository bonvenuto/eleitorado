"""Modelos e carga do manifesto de fontes (`fontes/*.yaml`)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

Cadencia = Literal["diaria", "semanal", "mensal"]


class _Modelo(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegraCompetencia(_Modelo):
    tipo: Literal["ano", "mes", "data_arquivo", "data_coleta"]
    inicio: int | None = None
    fim: str | None = None  # AAAA-MM, só para tipo "mes": última competência de série encerrada
    pagina: str | None = None

    @model_validator(mode="after")
    def _fim(self) -> RegraCompetencia:
        if self.fim is not None:
            if self.tipo != "mes":
                raise ValueError("competencia.fim só vale para tipo 'mes'")
            if not re.fullmatch(r"\d{4}-\d{2}", self.fim):
                raise ValueError("competencia.fim deve ser AAAA-MM")
        return self


class RegraCadencia(_Modelo):
    corrente: Cadencia
    anteriores: Cadencia | None = None


class Formato(_Modelo):
    tipo: Literal["csv", "json"]
    compressao: Literal["zip"] | None = None
    arquivo: str | None = None
    encoding: str = "utf-8"
    delimitador: str = ";"
    linhas_a_pular: int = 0


class Iteracao(_Modelo):
    parametro: str
    valores: Literal["legislaturas"]
    inicio: int


class Recurso(_Modelo):
    id: str
    descricao: str
    fonte_oficial: str
    condicoes_uso: str
    adaptador: Literal["arquivo", "api_json"]
    url: str
    parametros: dict[str, str | int] = {}
    publicacao: Literal["snapshot", "por_competencia"]
    competencia: RegraCompetencia
    cadencia: RegraCadencia
    formato: Formato
    paginacao: Literal["links_next", "nenhuma"] = "nenhuma"
    iteracao: Iteracao | None = None
    registros: str | None = None
    acesso: Literal["publico"] = "publico"

    @model_validator(mode="after")
    def _coerente(self) -> Recurso:
        regra = self.competencia
        if self.publicacao == "por_competencia":
            if regra.tipo not in ("ano", "mes") or regra.inicio is None:
                raise ValueError(
                    "por_competencia exige competencia.tipo 'ano' ou 'mes' com 'inicio'"
                )
            if self.cadencia.anteriores is None:
                raise ValueError("por_competencia exige cadencia.anteriores")
        elif regra.tipo in ("ano", "mes"):
            raise ValueError("snapshot exige competencia.tipo 'data_arquivo' ou 'data_coleta'")
        if regra.tipo == "data_arquivo" and not regra.pagina:
            raise ValueError("competencia.tipo 'data_arquivo' exige 'pagina'")
        if self.adaptador == "arquivo" and self.formato.tipo != "csv":
            raise ValueError("adaptador 'arquivo' exige formato.tipo 'csv'")
        if self.adaptador == "api_json" and self.formato.tipo != "json":
            raise ValueError("adaptador 'api_json' exige formato.tipo 'json'")
        return self


class Orgao(_Modelo):
    orgao: str
    nome: str
    portal: str
    recursos: list[Recurso]


@dataclass(frozen=True)
class RecursoCompleto:
    orgao: str
    recurso: Recurso

    @property
    def id(self) -> str:
        return f"{self.orgao}.{self.recurso.id}"


class ErroManifesto(Exception):
    """Manifesto inválido ou recurso inexistente."""


@dataclass(frozen=True)
class Manifesto:
    recursos: dict[str, RecursoCompleto]

    def obter(self, recurso_id: str) -> RecursoCompleto:
        try:
            return self.recursos[recurso_id]
        except KeyError:
            disponiveis = ", ".join(sorted(self.recursos))
            raise ErroManifesto(
                f"recurso desconhecido: {recurso_id} (disponíveis: {disponiveis})"
            ) from None

    def todos(self) -> list[RecursoCompleto]:
        return [self.recursos[chave] for chave in sorted(self.recursos)]


def carregar_manifesto(diretorio: Path) -> Manifesto:
    arquivos = sorted(diretorio.glob("*.yaml"))
    if not arquivos:
        raise ErroManifesto(f"nenhum arquivo .yaml em {diretorio}")
    recursos: dict[str, RecursoCompleto] = {}
    for arquivo in arquivos:
        dados = yaml.safe_load(arquivo.read_text(encoding="utf-8"))
        try:
            orgao = Orgao.model_validate(dados)
        except ValidationError as erro:
            raise ErroManifesto(f"{arquivo.name}: {erro}") from erro
        for recurso in orgao.recursos:
            completo = RecursoCompleto(orgao.orgao, recurso)
            if completo.id in recursos:
                raise ErroManifesto(f"recurso duplicado: {completo.id}")
            recursos[completo.id] = completo
    return Manifesto(recursos)
