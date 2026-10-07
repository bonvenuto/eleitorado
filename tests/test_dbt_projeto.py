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
    # Listagem apenas compila: seleção sintética explícita mantém os gates produtivos.
    familias = [
        "candidaturas",
        "bens",
        "receitas",
        "contratadas",
        "pagamentos",
        "doador_originario",
    ]
    fontes = {familia: [(projeto / f"{familia}.parquet").as_posix()] for familia in familias}
    variaveis = {
        "tse_fontes": fontes,
        "tse_proveniencia": {
            caminhos[0]: {
                "ano_arquivo": 2024,
                "versao_id": "a" * 64,
                "layout_id": f"tse:{familia}:2024:v1",
            }
            for familia, caminhos in fontes.items()
        },
    }
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
            "--vars",
            json.dumps(variaveis),
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
        env={**__import__("os").environ, "ELEITORADO_LAGO": str(projeto)},
    )
    linhas = [json.loads(linha) for linha in saida.stdout.splitlines() if linha.startswith("{")]
    return {
        linha["name"]: linha["schema"]
        for linha in linhas
        if linha["name"] in ("com_schema", "sem_schema")
    }


@pytest.mark.parametrize("target", ["prod", "dev", "ci"])
def test_schema_e_sempre_o_configurado(projeto, target):
    # cada target tem o próprio arquivo .duckdb: não há prefixo por usuário nem por ambiente
    assert _schemas(projeto, target) == {"com_schema": "staging", "sem_schema": "main"}


def test_targets_usam_duckdb_com_arquivos_separados():
    import yaml

    perfil = yaml.safe_load((RAIZ / "dbt" / "profiles.yml").read_text(encoding="utf-8"))
    saidas = perfil["eleitorado"]["outputs"]
    assert {nome: saida["type"] for nome, saida in saidas.items()} == {
        "dev": "duckdb",
        "prod": "duckdb",
        "agente": "duckdb",
        "ci": "duckdb",
    }
    assert len({saida["path"] for saida in saidas.values()}) == 4
