from pathlib import Path

from agente.config import carregar


def test_config_padrao(tmp_path: Path):
    config = carregar(raiz=tmp_path)
    assert config.lago == (tmp_path / "dados-agente").resolve()
    assert config.banco == config.lago / "agente.duckdb"
    assert config.investigacoes == (tmp_path / "investigacoes").resolve()
    assert config.prefixo_gcs == "paralelo/"
    assert config.modelo is None
    assert config.diretorios_permitidos() == [
        config.lago / "raw",
        config.lago / "meta",
        config.lago / "publico",
    ]
    assert config.orcamento(None).ciclos == 300
    assert config.orcamento("emendas no PI").ciclos == 300
