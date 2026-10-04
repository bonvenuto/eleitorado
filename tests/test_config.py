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
    assert config.dataset("raw_cgu") == "raw_cgu_dev"
    assert config.prefixo_gcs == "dev/"


def test_config_de_producao_nao_tem_sufixo():
    config = carregar_config(
        {"ELEITORADO_PROJETO": "p", "ELEITORADO_BUCKET": "b", "ELEITORADO_AMBIENTE": "prod"}
    )
    assert config.dataset("raw_cgu") == "raw_cgu"
    assert config.prefixo_gcs == ""


def test_config_sem_bucket_falha():
    with pytest.raises(ErroConfig, match="ELEITORADO_BUCKET"):
        carregar_config({"ELEITORADO_PROJETO": "p"})


def test_config_com_ambiente_invalido_falha():
    with pytest.raises(ErroConfig, match="dev ou prod"):
        carregar_config(
            {"ELEITORADO_PROJETO": "p", "ELEITORADO_BUCKET": "b", "ELEITORADO_AMBIENTE": "x"}
        )
