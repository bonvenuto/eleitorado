from __future__ import annotations

from pathlib import Path

import duckdb
import pytest


@pytest.fixture
def lago(tmp_path: Path, monkeypatch) -> Path:
    """Lago mínimo: um Parquet no raw, uma view relativa (como as do dbt) e uma tabela."""
    monkeypatch.chdir(tmp_path)
    raiz = tmp_path / "dados-agente"
    (raiz / "raw" / "cgu").mkdir(parents=True)
    (raiz / "meta").mkdir()
    (raiz / "publico").mkdir()
    (tmp_path / "fora").mkdir()
    duckdb.sql(
        "copy (select range as id, 'empresa ' || range as nome, range * 10.5 as valor "
        "from range(300)) to 'dados-agente/raw/cgu/x.parquet'"
    )
    duckdb.sql("copy (select 42 as segredo) to 'fora/segredo.parquet'")
    conexao = duckdb.connect(str(raiz / "agente.duckdb"))
    conexao.execute("create schema marts")
    conexao.execute(
        "create view marts.fornecedores as "
        "select * from read_parquet('dados-agente/raw/cgu/*.parquet')"
    )
    conexao.execute("create table marts.tabela as select 1 as um")
    conexao.close()
    return raiz
