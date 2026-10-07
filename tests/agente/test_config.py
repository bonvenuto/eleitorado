from pathlib import Path

import pytest

from agente.config import carregar


def test_config_padrao(tmp_path: Path):
    config = carregar(raiz=tmp_path)
    assert config.lago == (tmp_path / "dados-agente").resolve()
    assert config.banco == config.lago / "agente.duckdb"
    assert config.investigacoes == (tmp_path / "investigacoes").resolve()
    assert config.prefixo_gcs == ""
    assert config.modelo is None
    assert config.diretorios_permitidos() == [
        config.lago / "raw",
        config.lago / "meta",
        config.lago / "publico",
        *[
            config.lago / f"estado/tse/ci/{familia}/vazio"
            for familia in (
                "bens",
                "candidaturas",
                "contratadas",
                "doador_originario",
                "pagamentos",
                "receitas",
            )
        ],
    ]
    assert config.orcamento(None).ciclos == 300
    assert config.orcamento("emendas no PI").ciclos == 300


def test_permissoes_saida_c2_exata_e_bootstrap(tmp_path):
    import json

    config = carregar(raiz=tmp_path)
    config.lago.mkdir(parents=True)
    saida = config.lago / "estado/tse/publicacoes/preparadas/agente-1/marts"
    (config.lago / "preparo.json").write_text(
        json.dumps({"tse": {"execucao_id": "agente-1", "saida": str(saida)}})
    )
    permitidos = config.diretorios_permitidos()
    assert saida in permitidos
    assert config.lago / "estado/tse/publicacoes/preparadas" not in permitidos
    assert config.lago / "estado" not in permitidos
    for familia in (
        "bens",
        "candidaturas",
        "contratadas",
        "doador_originario",
        "pagamentos",
        "receitas",
    ):
        assert config.lago / f"estado/tse/ci/{familia}/vazio" in permitidos


@pytest.mark.parametrize(
    "execucao,saida",
    [
        ("../outra", None),
        ("agente-1", "fora"),
        ("agente-1", "estado/tse/publicacoes/preparadas/irma/marts"),
    ],
)
def test_permissoes_rejeitam_marca_c2_arbitraria(tmp_path, execucao, saida):
    import json

    config = carregar(raiz=tmp_path)
    config.lago.mkdir(parents=True)
    dados = {"execucao_id": execucao}
    if saida:
        dados["saida"] = str(config.lago / saida)
    (config.lago / "preparo.json").write_text(json.dumps({"tse": dados}))
    with pytest.raises(ValueError):
        config.diretorios_permitidos()


@pytest.mark.parametrize("tipo", ["is_symlink", "is_junction"])
def test_permissoes_rejeitam_componentes_simbolicos(tmp_path, monkeypatch, tipo):
    import json

    config = carregar(raiz=tmp_path)
    config.lago.mkdir(parents=True)
    (config.lago / "preparo.json").write_text(json.dumps({"tse": {"execucao_id": "agente-1"}}))
    original = getattr(Path, tipo)
    monkeypatch.setattr(Path, tipo, lambda p: p.name == "agente-1" or original(p))
    with pytest.raises(ValueError, match="simbólico|junction"):
        config.diretorios_permitidos()


def test_permissoes_bloqueiam_preparo_c2_pendente_mesmo_invalido(tmp_path):
    config = carregar(raiz=tmp_path)
    config.lago.mkdir(parents=True)
    (config.lago / "preparo-c2-pendente.json").write_bytes(b"invalido")
    with pytest.raises(ValueError, match="pendente"):
        config.diretorios_permitidos()
