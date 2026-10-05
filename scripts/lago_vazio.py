"""Lago vazio do CI: um Parquet sem linhas, só com o esquema, para cada fonte do dbt.

Os esquemas ficam em texto, em dbt/tests/lago_vazio/esquemas.json (versionado); os Parquets são
gerados a partir dele e não vão para o git.

    uv run python scripts/lago_vazio.py                   # gera os Parquets (o CI faz isso)
    uv run python scripts/lago_vazio.py --de-lago dados   # esquemas a partir de um lago real
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import duckdb

PASTA = Path(__file__).resolve().parents[1] / "dbt" / "tests" / "lago_vazio"
ESQUEMAS = PASTA / "esquemas.json"
TABELAS_META = ["meta/coletas", "meta/fontes"]


def extrair(lago: Path) -> dict[str, dict[str, str]]:
    tabelas = sorted(
        {
            arquivo.parent.parent.relative_to(lago).as_posix()
            for arquivo in lago.glob("raw/*/*/*/*.parquet")
        }
    )
    esquemas = {}
    for tabela in tabelas + TABELAS_META:
        padrao = (lago / tabela / "*" / "*.parquet").as_posix()
        colunas = duckdb.sql(
            f"describe select * from read_parquet('{padrao}', union_by_name = true)"
        ).fetchall()
        esquemas[tabela] = {nome: tipo for nome, tipo, *_ in colunas}
    return esquemas


def gerar(esquemas: dict[str, dict[str, str]]) -> None:
    for tabela, colunas in esquemas.items():
        destino = PASTA / tabela / "vazio" / "vazio.parquet"
        if destino.parent.exists():
            shutil.rmtree(destino.parent)
        destino.parent.mkdir(parents=True)
        definicao = ", ".join(f'"{nome}" {tipo}' for nome, tipo in colunas.items())
        conexao = duckdb.connect()
        conexao.execute(f"create table vazia ({definicao})")
        conexao.execute(f"copy vazia to '{destino.as_posix()}' (format parquet)")
        conexao.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--de-lago", type=Path, help="lago real de onde extrair os esquemas")
    args = parser.parse_args()
    if args.de_lago:
        ESQUEMAS.parent.mkdir(parents=True, exist_ok=True)
        ESQUEMAS.write_text(
            json.dumps(extrair(args.de_lago), ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
    gerar(json.loads(ESQUEMAS.read_text(encoding="utf-8")))


if __name__ == "__main__":
    main()
