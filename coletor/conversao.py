"""Conversão de CSV e de registros JSON para Parquet, com colunas de controle."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from coletor.hashes import json_canonico
from coletor.manifesto import Formato
from coletor.nomes import normalizar_cabecalho

CAMPOS_CONTROLE = [
    pa.field("_coleta_id", pa.string()),
    pa.field("_competencia", pa.string()),
    pa.field("_competencia_data", pa.date32()),
    pa.field("_linha", pa.int64()),
    pa.field("_arquivo_original", pa.string()),
    pa.field("_carregado_em", pa.timestamp("us", tz="UTC")),
]


@dataclass(frozen=True)
class Controle:
    coleta_id: str
    competencia: str
    competencia_data: date
    arquivo_original: str
    carregado_em: datetime


@dataclass(frozen=True)
class ResultadoConversao:
    linhas: int
    colunas: list[list[str]]


def _arrays_controle(controle: Controle, primeira_linha: int, quantidade: int) -> list[pa.Array]:
    return [
        pa.array([controle.coleta_id] * quantidade, pa.string()),
        pa.array([controle.competencia] * quantidade, pa.string()),
        pa.array([controle.competencia_data] * quantidade, pa.date32()),
        pa.array(range(primeira_linha, primeira_linha + quantidade), pa.int64()),
        pa.array([controle.arquivo_original] * quantidade, pa.string()),
        pa.array([controle.carregado_em] * quantidade, pa.timestamp("us", tz="UTC")),
    ]


def ler_cabecalho(caminho: Path, formato: Formato) -> list[str]:
    with caminho.open("r", encoding=formato.encoding, newline="") as arquivo:
        for _ in range(formato.linhas_a_pular):
            arquivo.readline()
        leitor = csv.reader(arquivo, delimiter=formato.delimitador)
        try:
            return next(leitor)
        except StopIteration:
            raise ValueError(f"arquivo sem cabeçalho: {caminho.name}") from None


def csv_para_parquet(
    origem: Path,
    destino: Path,
    formato: Formato,
    controle: Controle,
    tamanho_bloco: int = 16 << 20,
) -> ResultadoConversao:
    nomes, pares = normalizar_cabecalho(ler_cabecalho(origem, formato))
    esquema = pa.schema([pa.field(nome, pa.string()) for nome in nomes] + CAMPOS_CONTROLE)
    leitor = pacsv.open_csv(
        origem,
        read_options=pacsv.ReadOptions(
            encoding=formato.encoding,
            skip_rows=formato.linhas_a_pular + 1,
            column_names=nomes,
            block_size=tamanho_bloco,
        ),
        parse_options=pacsv.ParseOptions(delimiter=formato.delimitador, newlines_in_values=True),
        convert_options=pacsv.ConvertOptions(
            column_types={nome: pa.string() for nome in nomes}, strings_can_be_null=False
        ),
    )
    linhas = 0
    with pq.ParquetWriter(destino, esquema, compression="zstd") as escritor:
        for lote in leitor:
            quantidade = lote.num_rows
            colunas = list(lote.columns) + _arrays_controle(controle, linhas + 1, quantidade)
            escritor.write_batch(pa.RecordBatch.from_arrays(colunas, schema=esquema))
            linhas += quantidade
    return ResultadoConversao(linhas, pares)


def registros_para_parquet(
    registros: list[Any], destino: Path, controle: Controle
) -> ResultadoConversao:
    esquema = pa.schema([pa.field("payload", pa.string())] + CAMPOS_CONTROLE)
    quantidade = len(registros)
    payload = pa.array([json_canonico(registro) for registro in registros], pa.string())
    tabela = pa.Table.from_arrays(
        [payload, *_arrays_controle(controle, 1, quantidade)], schema=esquema
    )
    pq.write_table(tabela, destino, compression="zstd")
    chaves = sorted({chave for r in registros if isinstance(r, dict) for chave in r})
    return ResultadoConversao(quantidade, [[chave, chave] for chave in chaves])
