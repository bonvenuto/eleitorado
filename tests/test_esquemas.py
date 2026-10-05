import duckdb

from coletor.esquemas import garantir_fontes

ESQUEMAS = {
    "raw/cgu/licitacoes": {"numero_licitacao": "VARCHAR", "_competencia": "VARCHAR"},
    "raw/cgu/contratos": {"numero_do_contrato": "VARCHAR"},
}


def test_cria_parquet_vazio_so_para_fonte_sem_dados(tmp_path):
    existente = tmp_path / "raw/cgu/contratos/202607/c1.parquet"
    existente.parent.mkdir(parents=True)
    duckdb.sql(
        f"copy (select '1' as numero_do_contrato) to '{existente.as_posix()}' (format parquet)"
    )

    criadas = garantir_fontes(tmp_path, ESQUEMAS)

    assert criadas == ["raw/cgu/licitacoes"]
    vazio = tmp_path / "raw/cgu/licitacoes/vazio/vazio.parquet"
    assert duckdb.sql(f"select count(*) from '{vazio.as_posix()}'").fetchone() == (0,)
    colunas = [c[0] for c in duckdb.sql(f"describe select * from '{vazio.as_posix()}'").fetchall()]
    assert colunas == ["numero_licitacao", "_competencia"]
    assert not (tmp_path / "raw/cgu/contratos/vazio").exists()


def test_segunda_chamada_nao_recria(tmp_path):
    assert garantir_fontes(tmp_path, ESQUEMAS) == ["raw/cgu/licitacoes", "raw/cgu/contratos"]
    assert garantir_fontes(tmp_path, ESQUEMAS) == []
