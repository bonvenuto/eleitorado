"""Execução do dbt: `build` no pipeline e `docs generate` (linhagem) na publicação."""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import threading
from collections.abc import Callable, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

Executor = Callable[[list[str]], int]


@dataclass(frozen=True)
class ResultadoDbt:
    status: str  # "sucesso" ou "falha"
    testes_com_erro: int | None  # None quando o dbt não chegou a gravar run_results.json


def _encerrar_processo(processo: subprocess.Popen[bytes], espera_s: float = 15.0) -> None:
    """Encerra o filho dbt e aguarda para não deixar lock aberto no arquivo .duckdb."""
    if processo.poll() is not None:
        return
    processo.terminate()
    try:
        processo.wait(timeout=espera_s)
    except subprocess.TimeoutExpired:
        processo.kill()
        processo.wait()


def _executar_subprocesso(comando: list[str]) -> int:
    processo = subprocess.Popen(comando)
    sinais_anteriores: dict[int, object] = {}
    sinal_recebido: int | None = None
    if threading.current_thread() is threading.main_thread():
        sinais = [signal.SIGINT]
        if hasattr(signal, "SIGTERM"):
            sinais.append(signal.SIGTERM)

        def _propagar(numero: int, _frame: object) -> None:
            nonlocal sinal_recebido
            sinal_recebido = numero
            # Não chamar processo.wait() aqui: o wait() da thread principal segura _waitpid_lock.
            if processo.poll() is None:
                processo.terminate()

        for sig in sinais:
            sinais_anteriores[sig] = signal.getsignal(sig)
            signal.signal(sig, _propagar)
    try:
        while True:
            try:
                codigo = processo.wait(timeout=15.0 if sinal_recebido is not None else None)
                break
            except subprocess.TimeoutExpired:
                processo.kill()
        if sinal_recebido is not None and codigo >= 0:
            return 128 + sinal_recebido
        return codigo
    finally:
        _encerrar_processo(processo)
        for sig, anterior in sinais_anteriores.items():
            signal.signal(sig, anterior)


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
