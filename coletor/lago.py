"""Lago local em Parquet: raw por coleta e tabelas de controle (meta), consultadas com DuckDB.

O lago espelha o bucket privado (`raw/`, `meta/`, `estado/`); quem sincroniza é `estado.py`.
"""

from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Protocol

import pyarrow as pa
import pyarrow.parquet as pq

TIPOS = {
    "STRING": pa.string(),
    "INTEGER": pa.int64(),
    "BOOLEAN": pa.bool_(),
    "DATE": pa.date32(),
    "TIMESTAMP": pa.timestamp("us", tz="UTC"),
}


@dataclass(frozen=True)
class Coluna:
    nome: str
    tipo: str
    modo: str = "NULLABLE"


@dataclass(frozen=True)
class Particionamento:
    granularidade: Literal["DAY", "MONTH", "YEAR"]
    expiracao_dias: int | None = None

    def decorador(self, dia: date) -> str:
        formato = {"DAY": "%Y%m%d", "MONTH": "%Y%m", "YEAR": "%Y"}[self.granularidade]
        return dia.strftime(formato)


@dataclass(frozen=True)
class Carga:
    linhas: int
    caminho: str  # relativo à raiz do lago, como `raw/cgu/ceis/20261002/<coleta>.parquet`


class Warehouse(Protocol):
    def carregar_parquet(
        self,
        tabela: str,
        origem: Path,
        particionamento: Particionamento,
        dia: date,
        coleta_id: str,
    ) -> Carga:
        """Substitui a partição de `dia` pelo Parquet `origem`."""
        ...

    def garantir_tabela(self, tabela: str, colunas: list[Coluna]) -> None: ...

    def anexar_linhas(
        self, tabela: str, linhas: list[dict[str, Any]], colunas: list[Coluna]
    ) -> None: ...

    def substituir_linhas(
        self, tabela: str, linhas: list[dict[str, Any]], colunas: list[Coluna]
    ) -> None: ...

    def consultar(self, sql: str) -> list[dict[str, Any]]: ...


def _esquema(colunas: list[Coluna]) -> pa.Schema:
    return pa.schema([pa.field(c.nome, TIPOS[c.tipo]) for c in colunas])


def _valor(valor: Any, tipo: str) -> Any:
    """As linhas de meta chegam serializadas (datas em ISO); o Parquet guarda o tipo certo."""
    if valor is None or not isinstance(valor, str):
        return valor
    if tipo == "TIMESTAMP":
        return datetime.fromisoformat(valor)
    if tipo == "DATE":
        return date.fromisoformat(valor)
    return valor


def _tabela_arrow(linhas: list[dict[str, Any]], colunas: list[Coluna]) -> pa.Table:
    dados = {c.nome: [_valor(linha.get(c.nome), c.tipo) for linha in linhas] for c in colunas}
    return pa.Table.from_pydict(dados, schema=_esquema(colunas))


class LagoWarehouse:
    """`tabela` é um caminho relativo à raiz: `raw/cgu/ceis` ou `meta/coletas`."""

    def __init__(self, raiz: Path, hoje: date | None = None) -> None:
        self.raiz = raiz
        self._hoje = hoje
        self._esquemas: dict[str, list[Coluna]] = {}

    def carregar_parquet(
        self,
        tabela: str,
        origem: Path,
        particionamento: Particionamento,
        dia: date,
        coleta_id: str,
    ) -> Carga:
        particao = particionamento.decorador(dia)
        pasta = self.raiz / tabela / particao
        if pasta.exists():
            shutil.rmtree(pasta)  # a carga substitui a partição inteira
        pasta.mkdir(parents=True)
        destino = pasta / f"{coleta_id}.parquet"
        shutil.copyfile(origem, destino)
        carga = Carga(
            pq.ParquetFile(destino).metadata.num_rows, destino.relative_to(self.raiz).as_posix()
        )
        if particionamento.expiracao_dias is not None:
            self._expirar(self.raiz / tabela, particionamento.expiracao_dias)
        return carga

    def _expirar(self, pasta_tabela: Path, dias: int) -> None:
        """Apaga partições diárias com mais de `dias` dias (o raw guarda 60 dias de snapshots)."""
        limite = (self._hoje or date.today()) - timedelta(days=dias)
        for pasta in pasta_tabela.iterdir():
            try:
                dia = datetime.strptime(pasta.name, "%Y%m%d").date()
            except ValueError:
                continue
            if dia <= limite:
                shutil.rmtree(pasta)

    def garantir_tabela(self, tabela: str, colunas: list[Coluna]) -> None:
        self._esquemas[tabela] = colunas

    def anexar_linhas(
        self, tabela: str, linhas: list[dict[str, Any]], colunas: list[Coluna]
    ) -> None:
        self._esquemas.setdefault(tabela, colunas)
        dia = (self._hoje or date.today()).isoformat()
        pasta = self.raiz / tabela / dia
        pasta.mkdir(parents=True, exist_ok=True)
        pq.write_table(_tabela_arrow(linhas, colunas), pasta / f"{uuid.uuid4()}.parquet")

    def substituir_linhas(
        self, tabela: str, linhas: list[dict[str, Any]], colunas: list[Coluna]
    ) -> None:
        self._esquemas.setdefault(tabela, colunas)
        pasta = self.raiz / tabela
        if pasta.exists():
            shutil.rmtree(pasta)
        (pasta / "atual").mkdir(parents=True)
        pq.write_table(_tabela_arrow(linhas, colunas), pasta / "atual" / "dados.parquet")

    def consultar(self, sql: str) -> list[dict[str, Any]]:
        """Cada tabela registrada vira uma view com o último segmento do nome (`coletas`)."""
        import duckdb

        conexao = duckdb.connect()
        try:
            for tabela, colunas in self._esquemas.items():
                nome = tabela.rsplit("/", 1)[-1]
                arquivos = sorted((self.raiz / tabela).glob("*/*.parquet"))
                if arquivos:
                    lista = ", ".join(f"'{a.as_posix()}'" for a in arquivos)
                    conexao.execute(
                        f"create view {nome} as select * "
                        f"from read_parquet([{lista}], union_by_name = true)"
                    )
                else:
                    conexao.register(nome, _tabela_arrow([], colunas))
            cursor = conexao.execute(sql)
            nomes = [d[0] for d in cursor.description]
            return [dict(zip(nomes, linha, strict=True)) for linha in cursor.fetchall()]
        finally:
            conexao.close()
