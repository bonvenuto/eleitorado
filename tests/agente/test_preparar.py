from datetime import UTC, datetime

import duckdb
import pytest

from agente.caderno import Caderno, Caso, ConsultaChave
from agente.config import ConfigAgente, Orcamento
from agente.preparar import (
    ErroPreparo,
    ambiente,
    gerar_contexto,
    impressao_lago,
    ler_env,
    preparar,
    revisar_caderno,
)

ORCAMENTO = Orcamento(ciclos=10, minutos=10, hipoteses=2, rodadas_validacao=2)
AGORA = datetime(2026, 10, 6, 12, tzinfo=UTC)


@pytest.fixture
def config(lago, tmp_path):
    (tmp_path / ".env").write_text(
        "# comentário\nELEITORADO_PROJETO=proj\nELEITORADO_AMBIENTE=dev\nCLOUDSDK_CONFIG='c:/x'\n",
        encoding="utf-8",
    )
    return ConfigAgente(
        raiz=tmp_path,
        lago=lago,
        investigacoes=tmp_path / "investigacoes",
        prefixo_gcs="paralelo/",
        modelo=None,
        tempo_consulta_s=30,
        linhas_exibidas=20,
        linhas_salvas=1000,
        livre=ORCAMENTO,
        tema=ORCAMENTO,
    )


def test_ler_env(tmp_path, config):
    assert ler_env(tmp_path / ".env") == {
        "ELEITORADO_PROJETO": "proj",
        "ELEITORADO_AMBIENTE": "dev",
        "CLOUDSDK_CONFIG": "c:/x",
    }
    assert ler_env(tmp_path / "nao_existe") == {}


def test_ambiente_le_o_lago_de_producao(config):
    env = ambiente(config, {"PATH": "p"})
    assert env["PATH"] == "p" and env["ELEITORADO_PROJETO"] == "proj"
    assert env["ELEITORADO_AMBIENTE"] == "prod"
    assert env["ELEITORADO_PREFIXO"] == "paralelo/"
    assert env["ELEITORADO_LAGO"] == str(config.lago)


def test_impressao_muda_quando_o_lago_muda(config):
    antes = impressao_lago(config.lago)
    assert antes == impressao_lago(config.lago)
    (config.lago / "raw" / "cgu" / "novo.parquet").write_bytes(b"x")
    assert impressao_lago(config.lago) != antes


def test_contexto_lista_tabelas_colunas_e_linhas(config):
    texto = gerar_contexto(config)
    assert "## marts" in texto
    assert "`marts.fornecedores` (300 linhas): id BIGINT, nome VARCHAR" in texto


def test_preparar_roda_restaurar_e_dbt_so_quando_muda(config):
    chamadas = []

    def rodar(comando, env):
        chamadas.append(comando[3] if comando[2] == "coletor" else comando[2])
        assert env["ELEITORADO_AMBIENTE"] == "prod"
        return 0

    primeiro = preparar(config, {}, rodar, lambda: AGORA)
    assert chamadas == ["--target", "dbt"]  # restaurar (com --target agente) e dbt
    assert primeiro.dbt_rodou and primeiro.versao_dados["dbt"] == "sucesso"
    assert (config.investigacoes / "contexto.md").exists()
    chamadas.clear()
    segundo = preparar(config, {}, rodar, lambda: AGORA)
    assert chamadas == ["--target"] and not segundo.dbt_rodou
    assert segundo.versao_dados["lago"] == primeiro.versao_dados["lago"]


def test_preparar_falha_se_o_restaurar_falha(config):
    with pytest.raises(ErroPreparo, match="restaurar"):
        preparar(config, {}, lambda comando, env: 1, lambda: AGORA)


def test_revisar_caderno_acha_casos_que_mudaram(config):
    caderno = Caderno(config.caderno)
    sql = "select id, valor from marts.fornecedores where id < 10"
    for identificador, situacao, linhas in (
        ("igual", "confirmado", 10),
        ("mudou", "descartado", 9),
        ("aberto", "inconclusivo", 1),
    ):
        caderno.salvar(
            Caso(
                caso_id=identificador,
                titulo=identificador,
                tipo="insight estratégico",
                padrao="p",
                entidades={"x": [identificador]},
                situacao=situacao,
                consultas_chave=[ConsultaChave(sql=sql, linhas=linhas, soma=472.5 + 45)],
                atualizado_em=AGORA,
            )
        )
    revisar = revisar_caderno(config, caderno)
    assert [c.caso_id for c in revisar] == ["mudou"]


def test_tabela_do_banco_continua_so_de_leitura(config):
    gerar_contexto(config)
    conexao = duckdb.connect(str(config.banco))  # o contexto não deixou o banco travado
    conexao.close()


def test_corrigir_particoes_devolve_as_colunas_de_particao(tmp_path):
    from agente.preparar import corrigir_particoes

    pasta = tmp_path / "marts" / "fct_x"
    pasta.parent.mkdir(parents=True)  # o DuckDB não cria a pasta-mãe
    duckdb.sql(
        f"copy (select 'camara' as casa, 2024 as ano, 1.5 as valor) to '{pasta.as_posix()}' "
        "(format parquet, partition_by (casa, ano))"
    )
    banco = tmp_path / "b.duckdb"
    conexao = duckdb.connect(str(banco))
    conexao.execute("create schema marts")
    conexao.execute(
        f"create view marts.fct_x as select * from read_parquet('{pasta.as_posix()}/*/*/*.parquet')"
    )
    conexao.execute("create view marts.fct_y as select 1 as um")
    conexao.close()
    assert corrigir_particoes(banco) == ["fct_x"]
    conexao = duckdb.connect(str(banco))
    assert conexao.sql("select casa, ano, valor from marts.fct_x").fetchall() == [
        ("camara", 2024, 1.5)
    ]
    conexao.close()


def test_somar_colunas_decimais_e_float():
    from decimal import Decimal

    import pyarrow as pa

    from agente.preparar import _somar

    tabela = pa.table(
        {
            "valor": pa.array([Decimal("1.50"), Decimal("2.00")], pa.decimal128(38, 2)),
            "fator": [0.25, 0.25],
            "nome": ["a", "b"],
        }
    )
    assert _somar(tabela) == 4.0
    assert _somar(pa.table({"nome": ["a"]})) is None
