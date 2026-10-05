"""Tabelas de controle em `meta/` no lago: coletas, execuções e manifesto publicado."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any

from coletor.competencias import Competencia, data_brasilia
from coletor.lago import Coluna, Warehouse
from coletor.manifesto import Manifesto, RecursoCompleto

STATUS_SUCESSO = ("carregada", "sem_alteracao")

COLUNAS_COLETAS = [
    Coluna("coleta_id", "STRING", "REQUIRED"),
    Coluna("execucao_id", "STRING"),
    Coluna("orgao", "STRING", "REQUIRED"),
    Coluna("recurso", "STRING", "REQUIRED"),
    Coluna("competencia", "STRING"),
    Coluna("competencia_data", "DATE"),
    Coluna("destino", "STRING"),
    Coluna("url", "STRING"),
    Coluna("parametros", "STRING"),
    Coluna("iniciada_em", "TIMESTAMP", "REQUIRED"),
    Coluna("finalizada_em", "TIMESTAMP"),
    Coluna("status", "STRING", "REQUIRED"),
    Coluna("http_status", "INTEGER"),
    Coluna("http_last_modified", "STRING"),
    Coluna("http_etag", "STRING"),
    Coluna("bytes_arquivo", "INTEGER"),
    Coluna("linhas", "INTEGER"),
    Coluna("sha256_arquivo", "STRING"),
    Coluna("sha256_conteudo", "STRING"),
    Coluna("arquivo_original", "STRING"),
    Coluna("arquivo_carga", "STRING"),
    Coluna("colunas", "STRING"),
    Coluna("esquema_alterado", "BOOLEAN"),
    Coluna("erro", "STRING"),
    Coluna("versao_coletor", "STRING"),
]

COLUNAS_EXECUCOES = [
    Coluna("execucao_id", "STRING", "REQUIRED"),
    Coluna("origem", "STRING", "REQUIRED"),
    Coluna("iniciada_em", "TIMESTAMP", "REQUIRED"),
    Coluna("finalizada_em", "TIMESTAMP"),
    Coluna("status", "STRING", "REQUIRED"),
    Coluna("coletas_carregadas", "INTEGER"),
    Coluna("coletas_sem_alteracao", "INTEGER"),
    Coluna("coletas_nao_publicadas", "INTEGER"),
    Coluna("coletas_falha", "INTEGER"),
    Coluna("dbt_status", "STRING"),
    Coluna("dbt_testes_com_erro", "INTEGER"),
    Coluna("versao", "STRING"),
]

COLUNAS_FONTES = [
    Coluna("recurso_id", "STRING", "REQUIRED"),
    Coluna("orgao", "STRING", "REQUIRED"),
    Coluna("recurso", "STRING", "REQUIRED"),
    Coluna("descricao", "STRING"),
    Coluna("fonte_oficial", "STRING"),
    Coluna("condicoes_uso", "STRING"),
    Coluna("adaptador", "STRING"),
    Coluna("url", "STRING"),
    Coluna("publicacao", "STRING"),
    Coluna("competencia_tipo", "STRING"),
    Coluna("cadencia_corrente", "STRING"),
    Coluna("cadencia_anteriores", "STRING"),
    Coluna("publicado_em", "TIMESTAMP"),
]


def _serializar(valor: Any) -> Any:
    if isinstance(valor, datetime):
        return valor.isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    return valor


@dataclass
class RegistroColeta:
    coleta_id: str
    execucao_id: str
    orgao: str
    recurso: str
    destino: str
    iniciada_em: datetime
    versao_coletor: str
    competencia: str | None = None
    competencia_data: date | None = None
    url: str | None = None
    parametros: dict[str, Any] = field(default_factory=dict)
    finalizada_em: datetime | None = None
    status: str = "falha"
    http_status: int | None = None
    http_last_modified: str | None = None
    http_etag: str | None = None
    bytes_arquivo: int | None = None
    linhas: int | None = None
    sha256_arquivo: str | None = None
    sha256_conteudo: str | None = None
    arquivo_original: str | None = None
    arquivo_carga: str | None = None
    colunas: list[list[str]] | None = None
    esquema_alterado: bool | None = None
    erro: str | None = None

    @classmethod
    def novo(
        cls,
        execucao_id: str,
        recurso: RecursoCompleto,
        competencia: Competencia | None,
        inicio: datetime,
        versao: str,
        destino: str = "raw",
    ) -> RegistroColeta:
        registro = cls(
            coleta_id=str(uuid.uuid4()),
            execucao_id=execucao_id,
            orgao=recurso.orgao,
            recurso=recurso.recurso.id,
            destino=destino,
            iniciada_em=inicio,
            versao_coletor=versao,
        )
        if competencia is not None:
            registro.definir_competencia(competencia)
        return registro

    @property
    def recurso_id(self) -> str:
        return f"{self.orgao}.{self.recurso}"

    def definir_competencia(self, competencia: Competencia) -> None:
        self.competencia = competencia.rotulo
        self.competencia_data = competencia.data

    def finalizar(self, status: str, instante: datetime) -> RegistroColeta:
        self.status = status
        self.finalizada_em = instante
        return self

    def para_linha(self) -> dict[str, Any]:
        linha = {chave: _serializar(valor) for chave, valor in asdict(self).items()}
        linha["parametros"] = json.dumps(self.parametros, ensure_ascii=False)
        linha["colunas"] = (
            None if self.colunas is None else json.dumps(self.colunas, ensure_ascii=False)
        )
        return linha


@dataclass
class RegistroExecucao:
    execucao_id: str
    origem: str
    iniciada_em: datetime
    finalizada_em: datetime
    status: str
    coletas_carregadas: int
    coletas_sem_alteracao: int
    coletas_nao_publicadas: int
    coletas_falha: int
    versao: str
    dbt_status: str | None = None
    dbt_testes_com_erro: int | None = None

    def para_linha(self) -> dict[str, Any]:
        return {chave: _serializar(valor) for chave, valor in asdict(self).items()}


@dataclass
class Sucesso:
    finalizada_em: datetime
    sha256_conteudo: str | None
    competencia_data: date | None
    colunas: list[list[str]] | None


class HistoricoColetas:
    """Última coleta bem-sucedida de cada (recurso, competência)."""

    def __init__(self, sucessos: dict[tuple[str, str], Sucesso] | None = None) -> None:
        self._sucessos = dict(sucessos or {})

    def ultimo_sha(self, recurso_id: str, competencia: str) -> str | None:
        sucesso = self._sucessos.get((recurso_id, competencia))
        return sucesso.sha256_conteudo if sucesso else None

    def ultima_data_sucesso(self, recurso_id: str, competencia: str | None = None) -> date | None:
        instantes = [
            sucesso.finalizada_em
            for (rid, comp), sucesso in self._sucessos.items()
            if rid == recurso_id and (competencia is None or comp == competencia)
        ]
        return data_brasilia(max(instantes)) if instantes else None

    def colunas_referencia(
        self, recurso_id: str, competencia: Competencia
    ) -> list[list[str]] | None:
        """Colunas da mesma competência; senão, da competência anterior mais próxima."""
        mesma = self._sucessos.get((recurso_id, competencia.rotulo))
        if mesma is not None and mesma.colunas is not None:
            return mesma.colunas
        anteriores = [
            sucesso
            for (rid, _), sucesso in self._sucessos.items()
            if rid == recurso_id
            and sucesso.colunas is not None
            and sucesso.competencia_data is not None
            and sucesso.competencia_data < competencia.data
        ]
        if not anteriores:
            return None
        return max(anteriores, key=lambda s: (s.competencia_data, s.finalizada_em)).colunas

    def registrar(self, registro: RegistroColeta) -> None:
        recarga_no_raw = registro.status == "recarregada" and registro.destino == "raw"
        if registro.status not in STATUS_SUCESSO and not recarga_no_raw:
            return
        if registro.competencia is None:
            return
        chave = (registro.recurso_id, registro.competencia)
        anterior = self._sucessos.get(chave)
        colunas = registro.colunas if registro.status in ("carregada", "recarregada") else None
        if colunas is None and anterior is not None:
            colunas = anterior.colunas
        assert registro.finalizada_em is not None
        self._sucessos[chave] = Sucesso(
            registro.finalizada_em, registro.sha256_conteudo, registro.competencia_data, colunas
        )


SQL_HISTORICO = """
WITH sucesso AS (
  SELECT orgao, recurso, competencia, competencia_data, finalizada_em, sha256_conteudo,
         ROW_NUMBER() OVER (
           PARTITION BY orgao, recurso, competencia ORDER BY finalizada_em DESC) AS ordem
  FROM coletas
  WHERE status IN ('carregada', 'sem_alteracao', 'recarregada') AND destino = 'raw'
),
carga AS (
  SELECT orgao, recurso, competencia, colunas,
         ROW_NUMBER() OVER (
           PARTITION BY orgao, recurso, competencia ORDER BY finalizada_em DESC) AS ordem
  FROM coletas
  WHERE status IN ('carregada', 'recarregada') AND destino = 'raw'
)
SELECT s.orgao, s.recurso, s.competencia, s.competencia_data, s.finalizada_em,
       s.sha256_conteudo, c.colunas
FROM sucesso AS s
LEFT JOIN carga AS c
  ON c.orgao = s.orgao AND c.recurso = s.recurso AND c.competencia = s.competencia AND c.ordem = 1
WHERE s.ordem = 1
"""


class RepositorioMeta:
    tabela_coletas = "meta/coletas"
    tabela_execucoes = "meta/execucoes"
    tabela_fontes = "meta/fontes"

    def __init__(self, warehouse: Warehouse) -> None:
        self._warehouse = warehouse

    def preparar(self) -> None:
        self._warehouse.garantir_tabela(self.tabela_coletas, COLUNAS_COLETAS)
        self._warehouse.garantir_tabela(self.tabela_execucoes, COLUNAS_EXECUCOES)
        self._warehouse.garantir_tabela(self.tabela_fontes, COLUNAS_FONTES)

    def carregar_historico(self) -> HistoricoColetas:
        sucessos: dict[tuple[str, str], Sucesso] = {}
        for linha in self._warehouse.consultar(SQL_HISTORICO):
            colunas = json.loads(linha["colunas"]) if linha.get("colunas") else None
            chave = (f"{linha['orgao']}.{linha['recurso']}", linha["competencia"])
            sucessos[chave] = Sucesso(
                linha["finalizada_em"], linha["sha256_conteudo"], linha["competencia_data"], colunas
            )
        return HistoricoColetas(sucessos)

    def registrar_coleta(self, registro: RegistroColeta) -> None:
        self._warehouse.anexar_linhas(self.tabela_coletas, [registro.para_linha()], COLUNAS_COLETAS)

    def registrar_execucao(self, registro: RegistroExecucao) -> None:
        self._warehouse.anexar_linhas(
            self.tabela_execucoes, [registro.para_linha()], COLUNAS_EXECUCOES
        )

    def publicar_fontes(self, manifesto: Manifesto, instante: datetime) -> None:
        linhas = [
            {
                "recurso_id": rc.id,
                "orgao": rc.orgao,
                "recurso": rc.recurso.id,
                "descricao": rc.recurso.descricao,
                "fonte_oficial": rc.recurso.fonte_oficial,
                "condicoes_uso": rc.recurso.condicoes_uso,
                "adaptador": rc.recurso.adaptador,
                "url": rc.recurso.url,
                "publicacao": rc.recurso.publicacao,
                "competencia_tipo": rc.recurso.competencia.tipo,
                "cadencia_corrente": rc.recurso.cadencia.corrente,
                "cadencia_anteriores": rc.recurso.cadencia.anteriores,
                "publicado_em": instante.isoformat(),
            }
            for rc in manifesto.todos()
        ]
        self._warehouse.substituir_linhas(self.tabela_fontes, linhas, COLUNAS_FONTES)
