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
        "tse_contexto": {"selecao_id": "a" * 64, "entradas_digest": "b" * 64},
        "tse_fontes": fontes,
        "tse_saida": (projeto / "saida-c2").as_posix(),
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


def test_target_prod_parametriza_memoria_threads_e_desativa_insertion_order():
    import yaml

    perfil = yaml.safe_load((RAIZ / "dbt" / "profiles.yml").read_text(encoding="utf-8"))
    prod = perfil["eleitorado"]["outputs"]["prod"]
    assert "ELEITORADO_DUCKDB_THREADS" in str(prod["threads"])
    assert "ELEITORADO_DUCKDB_MEMORIA" in str(prod["settings"]["memory_limit"])
    assert prod["settings"]["preserve_insertion_order"] is False


def test_fontes_em_atraso_erro_so_falha_grupo_diario():
    import re

    import duckdb

    con = duckdb.connect()
    con.execute(
        """
        create table monitor_fontes as
        select * from (values
            ('cgu.ceis', 'diario', 'diaria', timestamp '2026-10-01 00:00:00', 100, 30, 54),
            ('cgu.cnep', 'diario', 'diaria', timestamp '2026-11-24 00:00:00', 10, 30, 54),
            ('rfb.empresas', 'receita', 'mensal', timestamp '2026-10-01 00:00:00', 1200, 840, 960),
            ('tse.bens', 'tse', 'mensal', null, null, 840, 960)
        ) t(recurso_id, grupo, cadencia_corrente, ultimo_sucesso, atraso_horas,
            limite_aviso_horas, limite_erro_horas)
        """
    )

    def _rodar(caminho):
        sql = (RAIZ / caminho).read_text(encoding="utf-8")
        sql = re.sub(r"\{\{\s*config\([^)]*\)\s*\}\}", "", sql)
        sql = re.sub(r"\{\{\s*ref\('monitor_fontes'\)\s*\}\}", "monitor_fontes", sql)
        return [linha[0] for linha in con.execute(sql).fetchall()]

    assert _rodar("dbt/tests/fontes_em_atraso_erro.sql") == ["cgu.ceis"]
    assert set(_rodar("dbt/tests/fontes_em_atraso_aviso.sql")) == {
        "cgu.ceis",
        "rfb.empresas",
        "tse.bens",
    }
    con.close()
