"""Execução do `dbt build` pelo comando `coletor pipeline`."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
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


def rodar_dbt(
    diretorio: Path, target: str, executar: Executor = _executar_subprocesso
) -> ResultadoDbt:
    resultados = diretorio / "target" / "run_results.json"
    resultados.unlink(missing_ok=True)
    codigo = executar(
        [
            "dbt",
            "build",
            "--project-dir",
            str(diretorio),
            "--profiles-dir",
            str(diretorio),
            "--target",
            target,
        ]
    )
    return ResultadoDbt("sucesso" if codigo == 0 else "falha", _testes_com_erro(resultados))
