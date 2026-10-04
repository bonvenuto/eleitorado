import json

from coletor.dbt import ResultadoDbt, rodar_dbt


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
    resultado = rodar_dbt(tmp_path, "prod", _executor_que_grava(resultados, 0, chamadas))
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
    resultado = rodar_dbt(tmp_path, "prod", _executor_que_grava(resultados, 1, []))
    assert resultado == ResultadoDbt("falha", 2)


def test_resultado_antigo_nao_e_reaproveitado(tmp_path):
    antigo = tmp_path / "target" / "run_results.json"
    antigo.parent.mkdir()
    antigo.write_text(json.dumps({"results": [{"unique_id": "test.x", "status": "fail"}]}))
    resultado = rodar_dbt(tmp_path, "prod", lambda comando: 2)
    assert resultado == ResultadoDbt("falha", None)
