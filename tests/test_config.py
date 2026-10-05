from pathlib import Path

import pytest

from coletor.config import ErroConfig, carregar_config


def test_config_le_variaveis_e_aplica_padroes():
    config = carregar_config({"ELEITORADO_PROJETO": "p", "ELEITORADO_BUCKET": "b"})
    assert (config.regiao, config.ambiente, config.versao, config.origem) == (
        "southamerica-east1",
        "dev",
        "local",
        "manual",
    )
    assert config.prefixo_gcs == "dev/"
    assert (config.lago, config.publico) == (Path("dados"), Path("dados/publico"))


def test_config_de_producao_nao_tem_sufixo():
    config = carregar_config(
        {"ELEITORADO_PROJETO": "p", "ELEITORADO_BUCKET": "b", "ELEITORADO_AMBIENTE": "prod"}
    )
    assert config.prefixo_gcs == ""


def test_prefixo_do_paralelo_vem_antes_do_de_dev():
    base = {"ELEITORADO_PROJETO": "p", "ELEITORADO_BUCKET": "b", "ELEITORADO_PREFIXO": "paralelo/"}
    assert carregar_config({**base, "ELEITORADO_AMBIENTE": "prod"}).prefixo_gcs == "paralelo/"
    assert carregar_config(base).prefixo_gcs == "paralelo/dev/"


def test_prefixo_sem_barra_final_falha():
    with pytest.raises(ErroConfig, match="terminar com /"):
        carregar_config(
            {"ELEITORADO_PROJETO": "p", "ELEITORADO_BUCKET": "b", "ELEITORADO_PREFIXO": "x"}
        )


def test_config_sem_bucket_falha():
    with pytest.raises(ErroConfig, match="ELEITORADO_BUCKET"):
        carregar_config({"ELEITORADO_PROJETO": "p"})


def test_config_com_ambiente_invalido_falha():
    with pytest.raises(ErroConfig, match="dev ou prod"):
        carregar_config(
            {"ELEITORADO_PROJETO": "p", "ELEITORADO_BUCKET": "b", "ELEITORADO_AMBIENTE": "x"}
        )
