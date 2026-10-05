"""Testes contra o GCS e as fontes reais.

Rodar com: uv run --env-file .env pytest -m integracao

Usam o prefixo `dev/` do bucket e um lago local temporário.
"""

import os
from dataclasses import replace

import pytest

from coletor import estado
from coletor.coleta import coletar
from coletor.config import Config, carregar_config
from coletor.gcp import montar_dependencias
from coletor.manifesto import carregar_manifesto
from coletor.meta import RepositorioMeta
from tests.amostras import RAIZ

pytestmark = pytest.mark.integracao


@pytest.fixture
def config_dev(tmp_path) -> Config:
    config = carregar_config()
    assert config.ambiente == "dev", "os testes de integração só rodam com ELEITORADO_AMBIENTE=dev"
    return replace(config, lago=tmp_path / "lago", publico=tmp_path / "publico")


def test_coleta_real_do_cnep_e_idempotente(config_dev):
    deps = montar_dependencias(config_dev)
    try:
        repo = RepositorioMeta(deps.warehouse)
        repo.preparar()
        cnep = carregar_manifesto(RAIZ / "fontes").obter("cgu.cnep")
        historico = repo.carregar_historico()
        primeira = coletar(cnep, None, historico, deps, "integracao", forcar=True)
        repo.registrar_coleta(primeira)
        assert primeira.status == "carregada", primeira.erro
        assert primeira.linhas > 1000
        [contagem] = deps.warehouse.consultar(
            "select count(*) as n from read_parquet("
            f"'{config_dev.lago.as_posix()}/raw/cgu/cnep/*/*.parquet') "
            f"where _coleta_id = '{primeira.coleta_id}'"
        )
        assert contagem["n"] == primeira.linhas
        historico.registrar(primeira)
        segunda = coletar(cnep, None, historico, deps, "integracao")
        repo.registrar_coleta(segunda)
        assert segunda.status == "sem_alteracao"
    finally:
        deps.http.fechar()


def test_estado_vai_ao_gcs_e_volta_para_um_lago_vazio(config_dev, tmp_path):
    deps = montar_dependencias(config_dev)
    prefixo = f"dev/teste-estado-{os.getpid()}/"
    arquivo = config_dev.lago / "raw" / "teste" / "x" / "20261004" / "a.parquet"
    arquivo.parent.mkdir(parents=True)
    arquivo.write_bytes(b"conteudo")
    banco = tmp_path / "banco.duckdb"
    try:
        enviado = estado.salvar(deps.armazenamento, prefixo, config_dev.lago, banco)
        assert enviado.enviados == 1
        assert estado.salvar(deps.armazenamento, prefixo, config_dev.lago, banco).enviados == 0
        outro_lago = tmp_path / "outro"
        restaurado = estado.restaurar(deps.armazenamento, prefixo, outro_lago, banco)
        assert restaurado.baixados == 1
        assert (outro_lago / "raw/teste/x/20261004/a.parquet").read_bytes() == b"conteudo"
    finally:
        for caminho in deps.armazenamento.listar(prefixo):
            deps.armazenamento.apagar(caminho)
        deps.http.fechar()
