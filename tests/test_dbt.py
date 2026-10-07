import json
import pathlib

from coletor.dbt import ResultadoDbt, banco_do_target, gerar_linhagem, rodar_dbt


def _executor_que_grava(resultados: list[dict], codigo: int, chamadas: list[list[str]]):
    def executar(comando: list[str]) -> int:
        chamadas.append(comando)
        destino = comando[comando.index("--project-dir") + 1]
        alvo = __import__("pathlib").Path(destino) / "target"
        alvo.mkdir(parents=True, exist_ok=True)
        (alvo / "run_results.json").write_text(
            json.dumps({"results": resultados}), encoding="utf-8"
        )
        return codigo

    return executar


def test_build_com_sucesso(tmp_path):
    chamadas: list[list[str]] = []
    resultados = [{"unique_id": "model.eleitorado.a", "status": "success"}]
    resultado = rodar_dbt(
        tmp_path,
        "prod",
        tmp_path / "publico",
        executar=_executor_que_grava(resultados, 0, chamadas),
    )
    assert resultado == ResultadoDbt("sucesso", 0)
    assert chamadas[0][:2] == ["dbt", "build"]
    assert chamadas[0][-2:] == ["--target", "prod"]


def test_build_com_testes_falhando_conta_os_erros(tmp_path):
    resultados = [
        {"unique_id": "test.eleitorado.unico", "status": "fail"},
        {"unique_id": "test.eleitorado.nao_nulo", "status": "error"},
        {"unique_id": "test.eleitorado.aviso", "status": "warn"},
        {"unique_id": "model.eleitorado.a", "status": "error"},
    ]
    resultado = rodar_dbt(
        tmp_path, "prod", tmp_path / "publico", executar=_executor_que_grava(resultados, 1, [])
    )
    assert resultado == ResultadoDbt("falha", 2)


def test_resultado_antigo_nao_e_reaproveitado(tmp_path):
    antigo = tmp_path / "target" / "run_results.json"
    antigo.parent.mkdir()
    antigo.write_text(json.dumps({"results": [{"unique_id": "test.x", "status": "fail"}]}))
    resultado = rodar_dbt(tmp_path, "prod", tmp_path / "publico", executar=lambda comando: 2)
    assert resultado == ResultadoDbt("falha", None)


def test_build_do_pipeline_nao_roda_testes_unitarios(tmp_path):
    # unit tests são do CI: em produção, o de um incremental exige a tabela já existir
    chamadas: list[list[str]] = []
    rodar_dbt(tmp_path, "prod", tmp_path / "publico", executar=_executor_que_grava([], 0, chamadas))
    comando = chamadas[0]
    assert comando[comando.index("--exclude-resource-type") + 1] == "unit_test"


def test_build_cria_a_pasta_dos_marts_e_repassa_argumentos(tmp_path):
    chamadas: list[list[str]] = []
    publico = tmp_path / "publico"
    rodar_dbt(
        tmp_path,
        "prod",
        publico,
        ["--select", "staging"],
        executar=_executor_que_grava([], 0, chamadas),
    )
    assert (publico / "marts").is_dir()  # o DuckDB não cria a pasta do Parquet particionado
    assert chamadas[0][chamadas[0].index("--select") + 1] == "staging"


def test_linhagem_copia_a_pagina_estatica(tmp_path):
    def executar(comando: list[str]) -> int:
        assert comando[1:4] == ["docs", "generate", "--static"]
        (tmp_path / "target").mkdir()
        (tmp_path / "target" / "static_index.html").write_text("<html>linhagem</html>")
        return 0

    assert gerar_linhagem(tmp_path, "prod", tmp_path / "publico", executar)
    assert (tmp_path / "publico" / "linhagem" / "index.html").read_text() == "<html>linhagem</html>"


def test_linhagem_com_falha_nao_publica_nada(tmp_path):
    assert not gerar_linhagem(tmp_path, "prod", tmp_path / "publico", lambda comando: 2)
    assert not (tmp_path / "publico").exists()


def test_banco_de_cada_target():
    lago = pathlib.Path("dados")
    assert banco_do_target(lago, "prod") == lago / "eleitorado.duckdb"
    assert banco_do_target(lago, "dev") == lago / "dev.duckdb"


def test_linhagem_mesmas_vars(tmp_path):
    vars_dbt = {"tse_fontes": {"bens": ["fixado.parquet"]}, "tse_saida": "privado/marts"}
    argumentos = ["--vars", json.dumps(vars_dbt), "--target-path", str(tmp_path / "exclusivo")]

    def executar(comando):
        assert comando[comando.index("--vars") + 1] == argumentos[1]
        alvo = pathlib.Path(comando[comando.index("--target-path") + 1])
        alvo.mkdir()
        (alvo / "static_index.html").write_text("linhagem fixada")
        return 0

    assert gerar_linhagem(tmp_path, "ci", tmp_path / "publico", executar, argumentos)


def test_build_captura_artefatos_no_target_exclusivo(tmp_path):
    alvo = tmp_path / "exclusivo"
    chamadas = []

    def executar(comando):
        alvo.mkdir()
        (alvo / "run_results.json").write_text('{"results": []}')
        return 0

    resultado = rodar_dbt(
        tmp_path,
        "ci",
        tmp_path / "publico",
        ["--target-path", str(alvo)],
        executar,
        capturar=lambda comando, retorno, caminho: chamadas.append((comando, retorno, caminho)),
    )
    assert resultado == ResultadoDbt("sucesso", 0)
    assert chamadas[0][1:] == (0, alvo)


def test_ambiente_dbt_absoluto_e_restaurado_na_falha(tmp_path, monkeypatch):
    import os

    import pytest

    from coletor.dbt import ambiente_dbt

    monkeypatch.setenv("ELEITORADO_LAGO", "relativo-anterior")
    monkeypatch.delenv("ELEITORADO_PUBLICO", raising=False)
    with pytest.raises(RuntimeError), ambiente_dbt(tmp_path / "lago", tmp_path / "publico"):
        assert os.environ["ELEITORADO_LAGO"] == (tmp_path / "lago").as_posix()
        assert os.environ["ELEITORADO_PUBLICO"] == (tmp_path / "publico").as_posix()
        raise RuntimeError("falha operacional")
    assert os.environ["ELEITORADO_LAGO"] == "relativo-anterior"
    assert "ELEITORADO_PUBLICO" not in os.environ
