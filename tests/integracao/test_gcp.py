"""Testes contra o GCP e as fontes reais. Rodar com: uv run --env-file .env pytest -m integracao"""

import uuid
from datetime import UTC, datetime

import pytest

from coletor.coleta import coletar
from coletor.competencias import data_brasilia
from coletor.config import Config, carregar_config
from coletor.conversao import Controle, csv_para_parquet
from coletor.gcp import montar_dependencias
from coletor.manifesto import Formato, carregar_manifesto
from coletor.meta import RepositorioMeta
from coletor.warehouse import Particionamento
from tests.amostras import RAIZ

pytestmark = pytest.mark.integracao


@pytest.fixture
def config_dev() -> Config:
    config = carregar_config()
    assert config.ambiente == "dev", "os testes de integração só rodam com ELEITORADO_AMBIENTE=dev"
    return config


def test_coleta_real_do_cnep_e_idempotente(config_dev):
    deps = montar_dependencias(config_dev)
    try:
        repo = RepositorioMeta(deps.warehouse, config_dev)
        repo.preparar()
        cnep = carregar_manifesto(RAIZ / "fontes").obter("cgu.cnep")
        historico = repo.carregar_historico()
        primeira = coletar(cnep, None, historico, deps, "integracao", forcar=True)
        repo.registrar_coleta(primeira)
        assert primeira.status == "carregada", primeira.erro
        assert primeira.linhas > 1000
        tabela = f"{config_dev.projeto}.{config_dev.dataset('raw_cgu')}.cnep"
        [contagem] = deps.warehouse.consultar(
            f"SELECT COUNT(*) AS n FROM `{tabela}` WHERE _coleta_id = '{primeira.coleta_id}'"
        )
        assert contagem["n"] == primeira.linhas
        historico.registrar(primeira)
        segunda = coletar(cnep, None, historico, deps, "integracao")
        repo.registrar_coleta(segunda)
        assert segunda.status == "sem_alteracao"
    finally:
        deps.http.fechar()


def test_coluna_nova_e_coluna_ausente_entre_cargas(config_dev, tmp_path):
    from google.cloud import bigquery

    deps = montar_dependencias(config_dev)
    tabela = f"{config_dev.dataset('raw_cgu')}.teste_evolucao_{uuid.uuid4().hex[:8]}"
    dia = data_brasilia(datetime.now(UTC))
    try:
        for indice, cabecalho in enumerate(["A;B", "A;C"]):
            csv = tmp_path / f"{indice}.csv"
            csv.write_text(f"{cabecalho}\n1;2\n", encoding="utf-8")
            parquet = tmp_path / f"{indice}.parquet"
            controle = Controle(
                f"teste-{indice}", dia.isoformat(), dia, "gs://teste", datetime.now(UTC)
            )
            csv_para_parquet(csv, parquet, Formato(tipo="csv"), controle)
            uri = deps.armazenamento.enviar(parquet, f"dev/carga/teste/{uuid.uuid4()}.parquet")
            linhas = deps.warehouse.carregar_parquet(tabela, uri, Particionamento("DAY"), dia)
            assert linhas == 1
        resultado = deps.warehouse.consultar(f"SELECT a, b, c FROM `{config_dev.projeto}.{tabela}`")
        assert resultado == [{"a": "1", "b": None, "c": "2"}]
    finally:
        bigquery.Client(project=config_dev.projeto).delete_table(
            f"{config_dev.projeto}.{tabela}", not_found_ok=True
        )
        deps.http.fechar()
