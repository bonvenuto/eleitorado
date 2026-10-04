"""Cargas e consultas no BigQuery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Literal, Protocol


@dataclass(frozen=True)
class Coluna:
    nome: str
    tipo: str
    modo: str = "NULLABLE"


@dataclass(frozen=True)
class Particionamento:
    granularidade: Literal["DAY", "YEAR"]
    expiracao_dias: int | None = None

    def decorador(self, dia: date) -> str:
        return dia.strftime("%Y%m%d") if self.granularidade == "DAY" else dia.strftime("%Y")


class Warehouse(Protocol):
    def carregar_parquet(
        self, tabela: str, uri: str, particionamento: Particionamento, dia: date
    ) -> int:
        """Substitui a partição de `dia` com o Parquet em `uri`; devolve as linhas carregadas."""
        ...

    def garantir_tabela(
        self, tabela: str, colunas: list[Coluna], particao_por: str | None = None
    ) -> None: ...

    def anexar_linhas(
        self, tabela: str, linhas: list[dict[str, Any]], colunas: list[Coluna]
    ) -> None: ...

    def substituir_linhas(
        self, tabela: str, linhas: list[dict[str, Any]], colunas: list[Coluna]
    ) -> None: ...

    def consultar(self, sql: str) -> list[dict[str, Any]]: ...


class BigQueryWarehouse:
    """`tabela` é sempre `dataset.tabela`; o projeto vem do construtor."""

    def __init__(self, projeto: str, regiao: str, credenciais: Any = None) -> None:
        from google.cloud import bigquery

        self._bq = bigquery
        self._projeto = projeto
        self._cliente = bigquery.Client(project=projeto, location=regiao, credentials=credenciais)

    def _id(self, tabela: str) -> str:
        return f"{self._projeto}.{tabela}"

    def carregar_parquet(
        self, tabela: str, uri: str, particionamento: Particionamento, dia: date
    ) -> int:
        from google.api_core.exceptions import NotFound

        bigquery = self._bq
        config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.PARQUET,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        )
        try:
            self._cliente.get_table(self._id(tabela))
        except NotFound:
            destino = self._id(tabela)
            expiracao = (
                particionamento.expiracao_dias * 86_400_000
                if particionamento.expiracao_dias
                else None
            )
            config.time_partitioning = bigquery.TimePartitioning(
                type_=particionamento.granularidade,
                field="_competencia_data",
                expiration_ms=expiracao,
            )
        else:
            destino = f"{self._id(tabela)}${particionamento.decorador(dia)}"
            config.schema_update_options = [
                bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION,
                bigquery.SchemaUpdateOption.ALLOW_FIELD_RELAXATION,
            ]
        job = self._cliente.load_table_from_uri(uri, destino, job_config=config)
        job.result()
        return int(job.output_rows or 0)

    def garantir_tabela(
        self, tabela: str, colunas: list[Coluna], particao_por: str | None = None
    ) -> None:
        bigquery = self._bq
        objeto = bigquery.Table(self._id(tabela), schema=self._esquema(colunas))
        if particao_por:
            objeto.time_partitioning = bigquery.TimePartitioning(type_="DAY", field=particao_por)
        self._cliente.create_table(objeto, exists_ok=True)

    def anexar_linhas(
        self, tabela: str, linhas: list[dict[str, Any]], colunas: list[Coluna]
    ) -> None:
        self._carregar_json(tabela, linhas, colunas, self._bq.WriteDisposition.WRITE_APPEND)

    def substituir_linhas(
        self, tabela: str, linhas: list[dict[str, Any]], colunas: list[Coluna]
    ) -> None:
        self._carregar_json(tabela, linhas, colunas, self._bq.WriteDisposition.WRITE_TRUNCATE)

    def consultar(self, sql: str) -> list[dict[str, Any]]:
        return [dict(linha.items()) for linha in self._cliente.query(sql).result()]

    def _esquema(self, colunas: list[Coluna]) -> list[Any]:
        return [self._bq.SchemaField(c.nome, c.tipo, mode=c.modo) for c in colunas]

    def _carregar_json(
        self, tabela: str, linhas: list[dict[str, Any]], colunas: list[Coluna], disposicao: str
    ) -> None:
        bigquery = self._bq
        config = bigquery.LoadJobConfig(
            schema=self._esquema(colunas),
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            write_disposition=disposicao,
        )
        self._cliente.load_table_from_json(linhas, self._id(tabela), job_config=config).result()
