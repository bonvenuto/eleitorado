"""O projeto dbt resolve os schemas como a spec pede (sem conexão com o BigQuery)."""

import json
import shutil
import subprocess

import pytest

from tests.amostras import RAIZ


@pytest.fixture
def projeto(tmp_path):
    destino = tmp_path / "dbt"
    shutil.copytree(RAIZ / "dbt", destino, ignore=shutil.ignore_patterns("target", "logs"))
    modelos = destino / "models"
    (modelos / "com_schema.sql").write_text("{{ config(schema='staging') }} select 1 as a\n")
    (modelos / "sem_schema.sql").write_text("select 1 as a\n")
    return destino


def _schemas(projeto, target: str) -> dict[str, str]:
    saida = subprocess.run(
        [
            "dbt",
            "ls",
            "--project-dir",
            str(projeto),
            "--profiles-dir",
            str(projeto),
            "--target",
            target,
            "--resource-type",
            "model",
            "--output",
            "json",
            "--output-keys",
            "name",
            "schema",
            "--quiet",
        ],
        capture_output=True,
        text=True,
        check=True,
        env={**__import__("os").environ, "ELEITORADO_PROJETO": "projeto-teste"},
    )
    linhas = [json.loads(linha) for linha in saida.stdout.splitlines() if linha.startswith("{")]
    return {linha["name"]: linha["schema"] for linha in linhas}


def test_schemas_em_producao_sao_os_configurados(projeto):
    assert _schemas(projeto, "prod") == {"com_schema": "staging", "sem_schema": "marts"}


def test_schemas_em_dev_levam_o_prefixo_do_usuario(projeto, monkeypatch):
    monkeypatch.setenv("ELEITORADO_USUARIO_DBT", "angelo")
    assert _schemas(projeto, "dev") == {
        "com_schema": "dev_angelo_staging",
        "sem_schema": "dev_angelo",
    }
