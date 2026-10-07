"""Execução do dbt: `build` no pipeline e `docs generate` (linhagem) na publicação."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Callable, Sequence
from contextlib import contextmanager
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
    *,
    capturar: Callable[[list[str], int, Path], None] | None = None,
) -> ResultadoDbt:
    """`dbt build` sem testes unitários (que rodam no CI); os marts vão para `publico/marts`."""
    (publico / "marts").mkdir(parents=True, exist_ok=True)  # o DuckDB não cria a pasta
    alvo = _target_path(diretorio, argumentos)
    resultados = alvo / "run_results.json"
    resultados.unlink(missing_ok=True)
    comando = _comando(
        ["build", "--exclude-resource-type", "unit_test", *argumentos], diretorio, target
    )
    codigo = executar(comando)
    if capturar is not None:
        capturar(comando, codigo, alvo)
    return ResultadoDbt("sucesso" if codigo == 0 else "falha", _testes_com_erro(resultados))


def gerar_linhagem(
    diretorio: Path,
    target: str,
    publico: Path,
    executar: Executor = _executar_subprocesso,
    argumentos: Sequence[str] = (),
) -> bool:
    """`dbt docs generate --static` e cópia da página única para `publico/linhagem/index.html`."""
    if executar(_comando(["docs", "generate", "--static", *argumentos], diretorio, target)) != 0:
        return False
    destino = publico / "linhagem" / "index.html"
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_target_path(diretorio, argumentos) / "static_index.html", destino)
    return True


def _target_path(diretorio: Path, argumentos: Sequence[str]) -> Path:
    if "--target-path" in argumentos:
        caminho = Path(argumentos[argumentos.index("--target-path") + 1])
        return caminho if caminho.is_absolute() else diretorio / caminho
    return diretorio / "target"


@contextmanager
def ambiente_dbt(lago: Path, publico: Path):
    """Subprocessos seriais recebem caminhos absolutos; restaura ate apos falha.

    Nao usar concorrentemente: o ambiente e herdado pelo dbt e vale somente neste contexto.
    """
    variaveis = {
        "ELEITORADO_LAGO": lago.resolve().as_posix(),
        "ELEITORADO_PUBLICO": publico.resolve().as_posix(),
    }
    anteriores = {chave: os.environ.get(chave) for chave in variaveis}
    try:
        os.environ.update(variaveis)
        yield
    finally:
        for chave, valor in anteriores.items():
            if valor is None:
                os.environ.pop(chave, None)
            else:
                os.environ[chave] = valor
