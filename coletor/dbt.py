"""Execução do dbt: `build` no pipeline e `docs generate` (linhagem) na publicação."""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

Executor = Callable[[list[str]], int]


@dataclass(frozen=True)
class ResultadoDbt:
    status: str  # "sucesso" ou "falha"
    testes_com_erro: int | None  # None quando o dbt não chegou a gravar run_results.json


def _executar_subprocesso(comando: list[str]) -> int:
    return subprocess.run(comando, check=False).returncode


def _testes_com_erro(caminho: Path) -> int | None:
    if not caminho.exists():
        return None
    resultados = json.loads(caminho.read_text(encoding="utf-8")).get("results", [])
    return sum(
        1
        for resultado in resultados
        if str(resultado.get("unique_id", "")).startswith("test.")
        and resultado.get("status") in ("fail", "error")
    )


def banco_do_target(lago: Path, target: str) -> Path:
    """Arquivo .duckdb de cada target, como em dbt/profiles.yml."""
    return lago / ("eleitorado.duckdb" if target == "prod" else f"{target}.duckdb")


def _comando(subcomando: list[str], diretorio: Path, target: str) -> list[str]:
    return [
        "dbt",
        *subcomando,
        "--project-dir",
        str(diretorio),
        "--profiles-dir",
        str(diretorio),
        "--target",
        target,
    ]


def rodar_dbt(
    diretorio: Path,
    target: str,
    publico: Path,
    argumentos: Sequence[str] = (),
    executar: Executor = _executar_subprocesso,
) -> ResultadoDbt:
    """`dbt build` sem testes unitários (que rodam no CI); os marts vão para `publico/marts`."""
    (publico / "marts").mkdir(parents=True, exist_ok=True)  # o DuckDB não cria a pasta
    resultados = diretorio / "target" / "run_results.json"
    resultados.unlink(missing_ok=True)
    codigo = executar(
        _comando(["build", "--exclude-resource-type", "unit_test", *argumentos], diretorio, target)
    )
    return ResultadoDbt("sucesso" if codigo == 0 else "falha", _testes_com_erro(resultados))


def gerar_linhagem(
    diretorio: Path, target: str, publico: Path, executar: Executor = _executar_subprocesso
) -> bool:
    """`dbt docs generate --static` e cópia da página única para `publico/linhagem/index.html`."""
    if executar(_comando(["docs", "generate", "--static"], diretorio, target)) != 0:
        return False
    destino = publico / "linhagem" / "index.html"
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(diretorio / "target" / "static_index.html", destino)
    return True
