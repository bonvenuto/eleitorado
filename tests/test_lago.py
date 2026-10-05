from datetime import UTC, date, datetime

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from coletor.lago import Coluna, LagoWarehouse, Particionamento
from coletor.meta import COLUNAS_COLETAS, SQL_HISTORICO

HOJE = date(2026, 10, 4)


def _parquet(caminho, colunas: dict[str, list]):
    pq.write_table(pa.table(colunas), caminho)
    return caminho


def test_carga_grava_um_arquivo_por_coleta_na_particao(tmp_path):
    lago = LagoWarehouse(tmp_path / "lago", hoje=HOJE)
    origem = _parquet(tmp_path / "x.parquet", {"a": ["1", "2"]})
    carga = lago.carregar_parquet(
        "raw/cgu/ceis", origem, Particionamento("DAY", 60), date(2026, 10, 2), "c1"
    )
    assert (carga.linhas, carga.caminho) == (2, "raw/cgu/ceis/20261002/c1.parquet")
    assert (tmp_path / "lago" / carga.caminho).exists()


def test_nova_carga_substitui_a_particao(tmp_path):
    lago = LagoWarehouse(tmp_path / "lago", hoje=HOJE)
    origem = _parquet(tmp_path / "x.parquet", {"a": ["1"]})
    anual = Particionamento("YEAR")
    lago.carregar_parquet("raw/camara/ceap", origem, anual, date(2025, 1, 1), "antiga")
    lago.carregar_parquet("raw/camara/ceap", origem, anual, date(2025, 1, 1), "nova")
    arquivos = sorted(p.name for p in (tmp_path / "lago/raw/camara/ceap/2025").iterdir())
    assert arquivos == ["nova.parquet"]


def test_snapshot_expira_depois_do_prazo_e_competencia_nao(tmp_path):
    lago = LagoWarehouse(tmp_path / "lago", hoje=HOJE)
    origem = _parquet(tmp_path / "x.parquet", {"a": ["1"]})
    snapshot = Particionamento("DAY", 60)
    lago.carregar_parquet("raw/cgu/ceis", origem, snapshot, date(2026, 8, 4), "velha")  # 61 dias
    lago.carregar_parquet("raw/cgu/ceis", origem, snapshot, date(2026, 8, 6), "dentro")
    lago.carregar_parquet("raw/cgu/ceis", origem, snapshot, date(2026, 10, 4), "hoje")
    assert sorted(p.name for p in (tmp_path / "lago/raw/cgu/ceis").iterdir()) == [
        "20260806",
        "20261004",
    ]
    lago.carregar_parquet("raw/camara/ceap", origem, Particionamento("YEAR"), date(2008, 1, 1), "c")
    assert (tmp_path / "lago/raw/camara/ceap/2008").exists()


def test_meta_guarda_os_tipos_e_responde_consultas(tmp_path):
    lago = LagoWarehouse(tmp_path / "lago", hoje=HOJE)
    colunas = [Coluna("id", "STRING"), Coluna("quando", "TIMESTAMP"), Coluna("dia", "DATE")]
    lago.garantir_tabela("meta/teste", colunas)
    lago.anexar_linhas(
        "meta/teste",
        [{"id": "a", "quando": "2026-10-04T10:00:00+00:00", "dia": "2026-10-02"}],
        colunas,
    )
    lago.anexar_linhas("meta/teste", [{"id": "b", "quando": None, "dia": None}], colunas)
    linhas = lago.consultar("select * from teste order by id")
    assert linhas[0]["id"] == "a"
    assert linhas[0]["quando"] == datetime(2026, 10, 4, 10, tzinfo=UTC)
    assert linhas[0]["dia"] == date(2026, 10, 2)
    assert linhas[1] == {"id": "b", "quando": None, "dia": None}
    assert len(list((tmp_path / "lago/meta/teste/2026-10-04").iterdir())) == 2


def test_historico_de_coletas_funciona_com_o_meta_vazio(tmp_path):
    lago = LagoWarehouse(tmp_path / "lago", hoje=HOJE)
    lago.garantir_tabela("meta/coletas", COLUNAS_COLETAS)
    assert lago.consultar(SQL_HISTORICO) == []


def test_substituir_troca_todo_o_conteudo(tmp_path):
    lago = LagoWarehouse(tmp_path / "lago", hoje=HOJE)
    colunas = [Coluna("id", "STRING")]
    lago.substituir_linhas("meta/fontes", [{"id": "a"}, {"id": "b"}], colunas)
    lago.substituir_linhas("meta/fontes", [{"id": "c"}], colunas)
    assert lago.consultar("select id from fontes") == [{"id": "c"}]


def test_cargas_com_colunas_diferentes_sao_lidas_juntas(tmp_path):
    # é assim que o dbt lê o raw: coluna nova ou ausente vira nulo nas outras cargas
    lago = LagoWarehouse(tmp_path / "lago", hoje=HOJE)
    snapshot = Particionamento("DAY", 60)
    um = _parquet(tmp_path / "1.parquet", {"a": ["1"], "b": ["2"]})
    dois = _parquet(tmp_path / "2.parquet", {"a": ["3"], "c": ["4"]})
    lago.carregar_parquet("raw/x/y", um, snapshot, date(2026, 10, 3), "c1")
    lago.carregar_parquet("raw/x/y", dois, snapshot, date(2026, 10, 4), "c2")
    padrao = (tmp_path / "lago/raw/x/y/*/*.parquet").as_posix()
    linhas = duckdb.sql(
        f"select a, b, c from read_parquet('{padrao}', union_by_name = true) order by a"
    ).fetchall()
    assert linhas == [("1", "2", None), ("3", None, "4")]
