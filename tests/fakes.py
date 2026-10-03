"""Dublês de GCS e BigQuery para testes sem nuvem."""

from __future__ import annotations

import shutil
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from coletor.armazenamento import caminho_de_uri
from coletor.warehouse import Coluna, Particionamento


class FakeArmazenamento:
    def __init__(self, raiz: Path, bucket: str = "bucket-teste") -> None:
        self.raiz = raiz
        self.bucket = bucket
        self.objetos: dict[str, Path] = {}

    def enviar(self, origem: Path, caminho: str) -> str:
        if caminho in self.objetos:
            return f"gs://{self.bucket}/{caminho}"
        destino = self.raiz / caminho
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origem, destino)
        self.objetos[caminho] = destino
        return f"gs://{self.bucket}/{caminho}"

    def baixar(self, caminho: str, destino: Path) -> None:
        shutil.copyfile(self.objetos[caminho], destino)

    def listar(self, prefixo: str) -> list[str]:
        return sorted(caminho for caminho in self.objetos if caminho.startswith(prefixo))


class FakeWarehouse:
    def __init__(self, armazenamento: FakeArmazenamento) -> None:
        self.armazenamento = armazenamento
        self.particoes: dict[tuple[str, str], pa.Table] = {}
        self.particionamentos: dict[str, Particionamento] = {}
        self.linhas: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.tabelas: set[str] = set()
        self.falha_na_carga: Exception | None = None
        self.resposta_consulta: list[dict[str, Any]] = []

    def carregar_parquet(
        self, tabela: str, uri: str, particionamento: Particionamento, dia: date
    ) -> int:
        if self.falha_na_carga is not None:
            raise self.falha_na_carga
        dados = pq.read_table(self.armazenamento.objetos[caminho_de_uri(uri)])
        self.particionamentos.setdefault(tabela, particionamento)
        self.particoes[(tabela, particionamento.decorador(dia))] = dados
        return dados.num_rows

    def garantir_tabela(
        self, tabela: str, colunas: list[Coluna], particao_por: str | None = None
    ) -> None:
        self.tabelas.add(tabela)

    def anexar_linhas(
        self, tabela: str, linhas: list[dict[str, Any]], colunas: list[Coluna]
    ) -> None:
        self.linhas[tabela].extend(linhas)

    def substituir_linhas(
        self, tabela: str, linhas: list[dict[str, Any]], colunas: list[Coluna]
    ) -> None:
        self.linhas[tabela] = list(linhas)

    def consultar(self, sql: str) -> list[dict[str, Any]]:
        return list(self.resposta_consulta)
