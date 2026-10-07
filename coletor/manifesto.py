"""Modelos e carga do manifesto de fontes (`fontes/*.yaml`)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

Cadencia = Literal["diaria", "semanal", "mensal", "anual"]


class _Modelo(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegraCompetencia(_Modelo):
    tipo: Literal["ano", "mes", "dia", "data_arquivo", "data_coleta"]
    inicio: int | None = None
    anos: list[int] | None = None
    fim: str | None = None  # AAAA-MM, só para tipo "mes": última competência de série encerrada
    pagina: str | None = None

    @model_validator(mode="after")
    def _fim(self) -> RegraCompetencia:
        if self.anos is not None:
            if self.tipo != "ano":
                raise ValueError("competencia.anos só vale para tipo 'ano'")
            if not self.anos or len(self.anos) != len(set(self.anos)):
                raise ValueError("competencia.anos exige valores únicos e não vazios")
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


class Recorte(_Modelo):
    """Adaptador `webdav_zip`: quais ZIPs da pasta baixar e como ler o CSV sem cabeçalho."""

    arquivos: str  # padrão (fnmatch) dos ZIPs na pasta da competência, como `Empresas*.zip`
    colunas: list[str]  # nomes das colunas, na ordem do layout da fonte
    raizes: str | None = None  # Parquet com a coluna `raiz`, relativo ao lago; None: tudo


class Iteracao(_Modelo):
    parametro: str
    valores: Literal["legislaturas"]
    inicio: int


class Recurso(_Modelo):
    id: str
    descricao: str
    fonte_oficial: str
    condicoes_uso: str
    adaptador: Literal["arquivo", "api_json", "webdav_zip", "api_detalhe", "tse_zip"]
    url: str
    url_detalhe: str | None = None  # api_detalhe: URL de cada registro, com `{id}`
    parametros: dict[str, str | int] = {}
    publicacao: Literal["snapshot", "por_competencia"]
    competencia: RegraCompetencia
    cadencia: RegraCadencia
    formato: Formato
    paginacao: Literal["links_next", "nenhuma", "pagina_total"] = "nenhuma"
    pagina_parametro: str = "pagina"
    total_paginas_campo: str = "totalPaginas"
    pausa_pagina_segundos: float = 0
    iteracao: Iteracao | None = None
    registros: str | None = None
    pausa_segundos: float = 0  # antes de cada coleta: fontes com proteção anti-robô
    limite_por_execucao: int | None = None  # competências por execução (carga histórica parcelada)
    acesso: Literal["publico"] = "publico"
    # "receita": coletado pelo workflow mensal da Receita, fora do pipeline diário
    grupo: Literal["diario", "receita"] = "diario"
    recorte: Recorte | None = None
    familias: dict[str, str] | None = None

    @model_validator(mode="after")
    def _coerente(self) -> Recurso:
        regra = self.competencia
        if self.publicacao == "por_competencia":
            if regra.tipo not in ("ano", "mes", "dia") or (
                regra.inicio is None and regra.anos is None
            ):
                raise ValueError(
                    "por_competencia exige competencia.tipo 'ano', 'mes' ou 'dia' "
                    "com 'inicio' ou 'anos'"
                )
            if self.cadencia.anteriores is None:
                raise ValueError("por_competencia exige cadencia.anteriores")
        elif regra.tipo in ("ano", "mes", "dia"):
            raise ValueError("snapshot exige competencia.tipo 'data_arquivo' ou 'data_coleta'")

        if regra.tipo == "data_arquivo" and not regra.pagina:
            raise ValueError("competencia.tipo 'data_arquivo' exige 'pagina'")
        if self.adaptador == "arquivo" and self.formato.tipo != "csv":
            raise ValueError("adaptador 'arquivo' exige formato.tipo 'csv'")
        if self.adaptador in ("api_json", "api_detalhe") and self.formato.tipo != "json":
            raise ValueError(f"adaptador '{self.adaptador}' exige formato.tipo 'json'")
        if self.adaptador == "api_detalhe" and (
            not self.url_detalhe or "{id}" not in self.url_detalhe
        ):
            raise ValueError("adaptador 'api_detalhe' exige url_detalhe com {id}")
        if self.adaptador == "webdav_zip":
            if self.recorte is None or self.formato.tipo != "csv":
                raise ValueError("adaptador 'webdav_zip' exige recorte e formato.tipo 'csv'")
            if regra.tipo != "data_arquivo":
                raise ValueError("adaptador 'webdav_zip' exige competencia.tipo 'data_arquivo'")
        elif self.recorte is not None:
            raise ValueError("recorte só vale para o adaptador 'webdav_zip'")
        if self.adaptador == "tse_zip":
            if not self.familias:
                raise ValueError("adaptador 'tse_zip' exige familias não vazio")
            if self.formato.tipo != "csv" or self.formato.compressao != "zip":
                raise ValueError("adaptador 'tse_zip' exige formato csv com compressao zip")
        elif self.familias is not None:
            raise ValueError("familias só vale para o adaptador 'tse_zip'")
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
