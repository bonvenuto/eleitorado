import pyarrow.parquet as pq
import pytest

from agente.consulta import ErroConsulta, abrir, executar, validar_sql
from agente.diario import Diario


@pytest.fixture
def conexao(lago):
    con = abrir(lago / "agente.duckdb", [lago / "raw", lago / "meta", lago / "publico"])
    yield con
    con.close()


@pytest.mark.parametrize(
    "sql",
    [
        "insert into marts.tabela values (2)",
        "update marts.tabela set um = 2",
        "delete from marts.tabela",
        "create table x as select 1",
        "attach 'outro.duckdb'",
        "install httpfs",
        "load httpfs",
        "copy marts.tabela to 'x.csv'",
        "pragma enable_profiling",
        "set enable_external_access = true",
        "select 1; select 2",
        "call duckdb_settings()",
    ],
)
def test_recusa_o_que_nao_e_uma_unica_leitura(sql):
    with pytest.raises(ErroConsulta):
        validar_sql(sql)


def test_aceita_select_e_with():
    assert validar_sql("select 1;") == "select 1"
    assert validar_sql("pragma version").startswith("SELECT")  # pragma de tabela é leitura
    assert validar_sql("with a as (select 1 as x) select * from a").startswith("with")


def test_le_view_do_lago_e_registra_no_diario(conexao, lago, tmp_path):
    diario = Diario(tmp_path / "investigacoes" / "inv1")
    resultado = executar(
        conexao,
        "select id, valor from marts.fornecedores order by id",
        diario,
        "investigador",
        linhas_exibidas=5,
    )
    assert (resultado.id, resultado.linhas, resultado.truncada) == ("q1", 300, False)
    assert "Consulta q1: 300 linha(s), mostrando as primeiras 5" in resultado.texto
    assert resultado.texto.count("\n| ") == 6  # cabeçalho + 5 linhas
    registro = diario.consultas()["q1"]
    assert (registro.linhas, registro.colunas, registro.papel) == (
        300,
        ["id", "valor"],
        "investigador",
    )
    assert pq.read_table(diario.caminho_resultado("q1")).num_rows == 300
    assert executar(conexao, "select 1", diario, "validador").id == "q2"


def test_trunca_o_resultado_salvo(conexao, tmp_path):
    diario = Diario(tmp_path / "inv")
    resultado = executar(
        conexao, "select * from range(50)", diario, "investigador", linhas_salvas=10
    )
    assert (resultado.linhas, resultado.truncada) == (10, True)
    assert "mais de 10" in resultado.texto


def test_arquivo_fora_do_lago_e_bloqueado(conexao, tmp_path):
    diario = Diario(tmp_path / "inv")
    for sql in (
        "select * from 'fora/segredo.parquet'",
        "select * from read_parquet('dados-agente/raw/../../fora/segredo.parquet')",
        "select * from read_text('dados-agente/agente.duckdb')",
    ):
        with pytest.raises(ErroConsulta):
            executar(conexao, sql, diario, "investigador")
    assert diario.consultas() == {}


def test_banco_so_de_leitura(lago, conexao):
    import duckdb

    with pytest.raises(duckdb.Error):
        conexao.execute("set enable_external_access = true")


def test_tempo_esgotado(conexao, tmp_path):
    with pytest.raises(ErroConsulta, match="tempo esgotado"):
        executar(
            conexao,
            "select count(*) from range(100000000) a, range(1000) b",
            Diario(tmp_path / "inv"),
            "investigador",
            tempo_maximo_s=0.5,
        )


def test_erro_de_sql_volta_como_mensagem(conexao, tmp_path):
    with pytest.raises(ErroConsulta, match="CatalogException"):
        executar(
            conexao, "select * from marts.nao_existe", Diario(tmp_path / "inv"), "investigador"
        )


def test_comentario_no_fim_nao_quebra_a_consulta(conexao, tmp_path):
    resultado = executar(
        conexao, "select 1 as um -- comentário", Diario(tmp_path / "inv"), "investigador"
    )
    assert resultado.linhas == 1


def test_texto_longo_e_cortado_com_aviso(conexao, tmp_path):
    resultado = executar(
        conexao,
        "select range as id, repeat('x', 300) as texto from range(200)",
        Diario(tmp_path / "inv"),
        "investigador",
        caracteres_maximos=5000,
    )
    assert len(resultado.texto) <= 5000 + 300
    assert "limite de texto" in resultado.texto
    assert resultado.linhas == 200  # o resultado salvo continua completo
