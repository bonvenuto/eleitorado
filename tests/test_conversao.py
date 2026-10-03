from datetime import UTC, date, datetime

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from coletor.conversao import Controle, csv_para_parquet, registros_para_parquet
from coletor.manifesto import Formato
from tests.amostras import CEAP_CSV, CEAPS_JSON, CNEP_CSV

CONTROLE = Controle(
    "coleta-1",
    "2026-10-02",
    date(2026, 10, 2),
    "gs://b/original.zip",
    datetime(2026, 10, 3, tzinfo=UTC),
)


def test_csv_windows_1252_com_quebra_de_linha_em_campo(tmp_path):
    origem = tmp_path / "cnep.csv"
    origem.write_bytes(CNEP_CSV.encode("cp1252"))
    resultado = csv_para_parquet(
        origem, tmp_path / "s.parquet", Formato(tipo="csv", encoding="cp1252"), CONTROLE
    )
    tabela = pq.read_table(tmp_path / "s.parquet")
    assert resultado.linhas == 2
    assert tabela.column("nome_do_sancionado").to_pylist() == [
        "Empresa Exemplo Comércio Ltda",
        "Pessoa Exemplo",
    ]
    assert tabela.column("observacoes").to_pylist() == ["linha 1\nlinha 2", ""]
    assert ["ABRAGÊNCIA DA SANÇÃO", "abragencia_da_sancao"] in resultado.colunas
    assert tabela.column("_linha").to_pylist() == [1, 2]
    assert tabela.column("_competencia_data").to_pylist() == [date(2026, 10, 2)] * 2
    assert tabela.schema.field("_carregado_em").type == pa.timestamp("us", tz="UTC")


def test_csv_utf8_com_bom_nao_contamina_o_primeiro_nome(tmp_path):
    origem = tmp_path / "ceap.csv"
    origem.write_bytes(("\ufeff" + CEAP_CSV).encode("utf-8"))
    resultado = csv_para_parquet(
        origem, tmp_path / "s.parquet", Formato(tipo="csv", encoding="utf-8-sig"), CONTROLE
    )
    tabela = pq.read_table(tmp_path / "s.parquet")
    assert resultado.colunas[0] == ["txNomeParlamentar", "txnomeparlamentar"]
    assert tabela.column("txtdescricao").to_pylist()[0] == "LOCOMOÇÃO, ALIMENTAÇÃO E  HOSPEDAGEM"
    assert tabela.column("cpf").to_pylist() == ["00000000191", ""]


def test_csv_com_linha_antes_do_cabecalho(tmp_path):
    origem = tmp_path / "ceaps.csv"
    origem.write_text(
        '"ULTIMA ATUALIZACAO";"06/08/2021"\n"ANO";"MES"\n"2008";"9"\n', encoding="cp1252"
    )
    formato = Formato(tipo="csv", encoding="cp1252", linhas_a_pular=1)
    resultado = csv_para_parquet(origem, tmp_path / "s.parquet", formato, CONTROLE)
    assert resultado.linhas == 1
    assert [normalizado for _, normalizado in resultado.colunas] == ["ano", "mes"]


def test_csv_so_com_cabecalho_gera_parquet_vazio(tmp_path):
    origem = tmp_path / "vazio.csv"
    origem.write_text('"A";"B"\n', encoding="utf-8")
    resultado = csv_para_parquet(origem, tmp_path / "s.parquet", Formato(tipo="csv"), CONTROLE)
    tabela = pq.read_table(tmp_path / "s.parquet")
    assert resultado.linhas == 0
    assert tabela.num_rows == 0
    assert tabela.column_names[:2] == ["a", "b"]


def test_csv_com_linha_de_tamanho_errado_falha(tmp_path):
    origem = tmp_path / "torto.csv"
    origem.write_text('"A";"B"\n"1";"2";"3"\n', encoding="utf-8")
    with pytest.raises(pa.ArrowInvalid):
        csv_para_parquet(origem, tmp_path / "s.parquet", Formato(tipo="csv"), CONTROLE)


def test_registros_viram_payload_json_e_colunas_sao_as_chaves(tmp_path):
    resultado = registros_para_parquet(CEAPS_JSON, tmp_path / "s.parquet", CONTROLE)
    tabela = pq.read_table(tmp_path / "s.parquet")
    assert resultado.linhas == 2
    assert tabela.column_names[0] == "payload"
    assert '"codSenador":3' in tabela.column("payload").to_pylist()[0]
    assert ["codSenador", "codSenador"] in resultado.colunas


def test_registros_vazios_geram_parquet_vazio(tmp_path):
    resultado = registros_para_parquet([], tmp_path / "s.parquet", CONTROLE)
    assert resultado.linhas == 0
    assert pq.read_table(tmp_path / "s.parquet").num_rows == 0


def test_csv_maior_que_um_bloco_numera_linhas_sem_saltos(tmp_path):
    origem = tmp_path / "grande.csv"
    linhas = ['"A";"B"'] + [f'"{i}";"texto {i}"' for i in range(5000)]
    origem.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    resultado = csv_para_parquet(
        origem, tmp_path / "s.parquet", Formato(tipo="csv"), CONTROLE, tamanho_bloco=4096
    )
    arquivo = pq.ParquetFile(tmp_path / "s.parquet")
    tabela = arquivo.read()
    assert arquivo.metadata.num_row_groups > 1
    assert resultado.linhas == 5000
    assert tabela.column("_linha").to_pylist() == list(range(1, 5001))
    assert tabela.column("a").to_pylist()[-1] == "4999"
