import duckdb
import pytest

from coletor import estado
from tests.fakes import FakeArmazenamento

PREFIXO = "paralelo/"


def _arquivo(lago, relativo, conteudo=b"x"):
    caminho = lago / relativo
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(conteudo)
    return caminho


@pytest.fixture
def gcs(tmp_path):
    return FakeArmazenamento(tmp_path / "gcs")


def test_salvar_envia_so_o_que_mudou(tmp_path, gcs):
    lago = tmp_path / "lago"
    _arquivo(lago, "raw/cgu/ceis/20261004/c1.parquet")
    _arquivo(lago, "meta/coletas/2026-10-04/a.parquet")
    banco = tmp_path / "nao-existe.duckdb"
    assert estado.salvar(gcs, PREFIXO, lago, banco).enviados == 2
    assert sorted(gcs.objetos) == [
        "paralelo/meta/coletas/2026-10-04/a.parquet",
        "paralelo/raw/cgu/ceis/20261004/c1.parquet",
    ]
    assert estado.salvar(gcs, PREFIXO, lago, banco).enviados == 0
    _arquivo(lago, "raw/cgu/ceis/20261004/c1.parquet", b"conteudo novo")
    assert estado.salvar(gcs, PREFIXO, lago, banco).enviados == 1


def test_salvar_apaga_do_bucket_o_que_saiu_do_raw_mas_nunca_do_meta(tmp_path, gcs):
    lago = tmp_path / "lago"
    banco = tmp_path / "nao-existe.duckdb"
    for dia in range(20261001, 20261005):
        _arquivo(lago, f"raw/cgu/ceis/{dia}/c.parquet")
    _arquivo(lago, "meta/coletas/2026-10-01/a.parquet")
    estado.salvar(gcs, PREFIXO, lago, banco)
    (lago / "raw/cgu/ceis/20261001/c.parquet").unlink()  # partição expirada no lago
    (lago / "meta/coletas/2026-10-01/a.parquet").unlink()  # cache incompleto não apaga meta
    resumo = estado.salvar(gcs, PREFIXO, lago, banco)
    assert resumo.apagados == 1
    assert "paralelo/raw/cgu/ceis/20261001/c.parquet" not in gcs.objetos
    assert "paralelo/meta/coletas/2026-10-01/a.parquet" in gcs.objetos


def test_salvar_recusa_apagar_quase_tudo(tmp_path, gcs):
    lago = tmp_path / "lago"
    banco = tmp_path / "nao-existe.duckdb"
    for dia in range(20):
        _arquivo(lago, f"raw/cgu/ceis/202610{dia:02d}/c.parquet")
    estado.salvar(gcs, PREFIXO, lago, banco)
    vazio = tmp_path / "lago-vazio"  # restauração que falhou
    _arquivo(vazio, "raw/cgu/ceis/20261020/c.parquet")
    with pytest.raises(estado.ErroSincronia, match="20 de 20"):
        estado.salvar(gcs, PREFIXO, vazio, banco)
    assert len(gcs.objetos) == 20


def test_restaurar_baixa_so_o_que_falta_ou_mudou(tmp_path, gcs):
    lago = tmp_path / "lago"
    banco = tmp_path / "banco.duckdb"
    _arquivo(lago, "raw/cgu/ceis/20261003/c.parquet", b"a")
    _arquivo(lago, "raw/cgu/ceis/20261004/c.parquet", b"b")
    _arquivo(lago, "meta/coletas/2026-10-04/a.parquet", b"m")
    estado.salvar(gcs, PREFIXO, lago, banco)
    cache = tmp_path / "cache"
    _arquivo(cache, "raw/cgu/ceis/20261003/c.parquet", b"a")  # já está no cache
    _arquivo(cache, "raw/cgu/ceis/20261004/c.parquet", b"velho")  # mudou no bucket
    resumo = estado.restaurar(gcs, PREFIXO, cache, banco)
    assert resumo.baixados == 2
    assert (cache / "raw/cgu/ceis/20261004/c.parquet").read_bytes() == b"b"
    assert (cache / "meta/coletas/2026-10-04/a.parquet").read_bytes() == b"m"


def test_historicos_vao_e_voltam_pelo_parquet(tmp_path, gcs):
    lago = tmp_path / "lago"
    banco = tmp_path / "banco.duckdb"
    conexao = duckdb.connect(str(banco))
    conexao.execute("create schema intermediate")
    conexao.execute(
        "create table intermediate.int_cgu__sancoes_eventos as "
        "select 'e1' as evento_id, 'ceis:1' as sancao_id, date '2026-10-02' as data_evento"
    )
    conexao.close()
    estado.salvar(gcs, PREFIXO, lago, banco)
    assert "paralelo/estado/historicos/int_cgu__sancoes_eventos.parquet" in gcs.objetos

    outro_lago, outro_banco = tmp_path / "outro", tmp_path / "outro.duckdb"
    estado.restaurar(gcs, PREFIXO, outro_lago, outro_banco)
    conexao = duckdb.connect(str(outro_banco))
    linhas = conexao.execute("select * from intermediate.int_cgu__sancoes_eventos").fetchall()
    conexao.close()
    assert [linha[:2] for linha in linhas] == [("e1", "ceis:1")]


def test_restaurar_sem_historicos_nao_cria_tabelas(tmp_path, gcs):
    banco = tmp_path / "banco.duckdb"
    estado.restaurar(gcs, PREFIXO, tmp_path / "lago", banco)
    conexao = duckdb.connect(str(banco))
    tabelas = conexao.execute("select table_name from information_schema.tables").fetchall()
    conexao.close()
    assert tabelas == []  # o primeiro dbt build cria os incrementais do zero


def test_salvar_aditivo_so_envia_o_que_nao_existe_e_nunca_apaga(tmp_path, gcs):
    # coleta fora do pipeline (Receita, do computador do mantenedor): o lago local pode estar
    # atrás do bucket, então nada é apagado nem sobrescrito, e os históricos não vão
    lago = tmp_path / "lago"
    _arquivo(lago, "raw/cgu/ceis/20261004/c1.parquet")
    _arquivo(lago, "estado/historicos/x.parquet")
    estado.salvar(gcs, "", lago, tmp_path / "nao-existe.duckdb")
    gcs.substituir(
        _arquivo(tmp_path / "outro", "a", b"do pipeline"), "raw/cgu/ceis/20261005/c2.parquet"
    )
    _arquivo(lago, "raw/cgu/ceis/20261004/c1.parquet", b"mudou localmente")
    _arquivo(lago, "raw/rfb/empresas/202609/r1.parquet")
    _arquivo(lago, "meta/coletas/2026-10-07/m.parquet")
    _arquivo(lago, "estado/historicos/x.parquet", b"historico local")
    resumo = estado.salvar(gcs, "", lago, tmp_path / "nao-existe.duckdb", aditivo=True)
    assert (resumo.enviados, resumo.apagados) == (2, 0)
    assert "raw/cgu/ceis/20261005/c2.parquet" in gcs.objetos  # não apagou o que o lago não tem
    assert gcs.objetos["raw/cgu/ceis/20261004/c1.parquet"].read_bytes() == b"x"  # não sobrescreveu
    assert gcs.objetos["estado/historicos/x.parquet"].read_bytes() == b"x"
    assert "raw/rfb/empresas/202609/r1.parquet" in gcs.objetos
    assert "meta/coletas/2026-10-07/m.parquet" in gcs.objetos
