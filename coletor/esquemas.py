"""Esquemas das fontes (dbt/tests/lago_vazio/esquemas.json) e Parquets vazios para fontes sem dados.

O dbt lê cada fonte com read_parquet('<tabela>/*/*.parquet'), que falha se não houver
arquivo nenhum, como na carga inicial de uma fonte nova cuja primeira coleta foi adiada.
Um Parquet vazio com o esquema da fonte mantém o pipeline de pé até a primeira carga.
"""

from __future__ import annotations

import json
from pathlib import Path

ARQUIVO_ESQUEMAS = Path("tests") / "lago_vazio" / "esquemas.json"  # relativo ao projeto dbt


def carregar_esquemas(projeto_dbt: Path) -> dict[str, dict[str, str]]:
    return json.loads((projeto_dbt / ARQUIVO_ESQUEMAS).read_text(encoding="utf-8"))


def gerar_vazio(destino: Path, colunas: dict[str, str]) -> None:
    import duckdb

    destino.parent.mkdir(parents=True, exist_ok=True)
    definicao = ", ".join(f'"{nome}" {tipo}' for nome, tipo in colunas.items())
    conexao = duckdb.connect()
    try:
        conexao.execute(f"create table vazia ({definicao})")
        conexao.execute(
            f"copy vazia to '{destino.as_posix().replace(chr(39), chr(39) * 2)}' (format parquet)"
        )
    finally:
        conexao.close()


def garantir_fontes(lago: Path, esquemas: dict[str, dict[str, str]]) -> list[str]:
    """Cria `<tabela>/vazio/vazio.parquet` para cada tabela sem nenhum Parquet;
    devolve as criadas.
    """
    criadas = []
    for tabela, colunas in esquemas.items():
        if tabela.startswith("raw/tse/"):
            continue  # TSE exige arquivos enumerados pelo preparo; nunca placeholder raw.
        pasta = lago / tabela
        if any(pasta.glob("*/*.parquet")):
            continue
        gerar_vazio(pasta / "vazio" / "vazio.parquet", colunas)
        criadas.append(tabela)
    return criadas
