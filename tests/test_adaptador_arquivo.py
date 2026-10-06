from datetime import date

import httpx
import pytest

from coletor.adaptadores import arquivo
from coletor.adaptadores.base import ErroColeta, extensao_de, preencher
from coletor.cgu import datas_candidatas, descobrir_data
from coletor.competencias import Competencia
from coletor.hashes import sha256_arquivo
from tests.amostras import CEAP_CSV, CNEP_CSV, PAGINA_CGU, recurso, zip_com

HOJE = date(2026, 10, 3)
PAGINA = "https://portaldatransparencia.gov.br/download-de-dados/cnep"


def test_descobre_a_data_na_pagina_da_cgu():
    assert descobrir_data(PAGINA_CGU) == date(2026, 10, 2)
    assert descobrir_data("<html>sem data</html>") is None


def test_datas_candidatas_comecam_pela_descoberta():
    assert datas_candidatas(date(2026, 10, 2), HOJE) == [
        date(2026, 10, 2),
        date(2026, 10, 1),
        date(2026, 9, 30),
    ]
    assert datas_candidatas(None, HOJE)[0] == date(2026, 10, 2)


def _mock_cgu(respx_mock, data: str, conteudo: bytes):
    respx_mock.get(f"{PAGINA}/{data}").mock(
        return_value=httpx.Response(
            302,
            headers={
                "Location": f"https://dadosabertos-download.cgu.gov.br/saida/cnep/{data}_CNEP.zip"
            },
        )
    )
    respx_mock.get(f"https://dadosabertos-download.cgu.gov.br/saida/cnep/{data}_CNEP.zip").mock(
        return_value=httpx.Response(200, content=conteudo)
    )


def test_arquivo_cgu_usa_a_data_anunciada(respx_mock, http, tmp_path):
    respx_mock.get(PAGINA).mock(return_value=httpx.Response(200, text=PAGINA_CGU))
    _mock_cgu(respx_mock, "20261002", zip_com({"20261002_CNEP.csv": CNEP_CSV.encode("cp1252")}))
    extracao = arquivo.extrair(recurso(), None, tmp_path, http, HOJE)
    assert extracao.competencia == Competencia.de_dia(date(2026, 10, 2))
    assert extracao.extensao == "zip"
    assert extracao.url.endswith("20261002_CNEP.zip")


def test_arquivo_cgu_sem_data_na_pagina_tenta_os_dias_anteriores(respx_mock, http, tmp_path):
    respx_mock.get(PAGINA).mock(return_value=httpx.Response(200, text="<html></html>"))
    respx_mock.get(f"{PAGINA}/20261002").mock(return_value=httpx.Response(403))
    _mock_cgu(respx_mock, "20261001", zip_com({"20261001_CNEP.csv": b"x"}))
    extracao = arquivo.extrair(recurso(), None, tmp_path, http, HOJE)
    assert extracao.competencia.rotulo == "2026-10-01"


def test_arquivo_cgu_indisponivel_em_todas_as_datas(respx_mock, http, tmp_path):
    respx_mock.get(PAGINA).mock(return_value=httpx.Response(500))
    respx_mock.get(url__startswith=f"{PAGINA}/").mock(return_value=httpx.Response(403))
    with pytest.raises(ErroColeta, match="2026-10-02=403"):
        arquivo.extrair(recurso(), None, tmp_path, http, HOJE)


def test_hash_de_conteudo_ignora_metadados_do_zip(tmp_path):
    rec = recurso()
    competencia = Competencia.de_dia(date(2026, 10, 2))
    conteudo = CNEP_CSV.encode("cp1252")
    hashes = []
    for indice, data_hora in enumerate([(2026, 10, 2, 18, 0, 0), (2026, 10, 3, 6, 0, 0)]):
        pasta = tmp_path / str(indice)
        pasta.mkdir()
        original = pasta / "original.zip"
        original.write_bytes(zip_com({"20261002_CNEP.csv": conteudo}, data_hora))
        preparado = arquivo.preparar(rec, competencia, original, pasta)
        hashes.append((sha256_arquivo(original), preparado.sha256_conteudo))
        assert preparado.csv is not None and preparado.csv.read_bytes() == conteudo
    assert hashes[0][0] != hashes[1][0]
    assert hashes[0][1] == hashes[1][1]


def test_zip_com_membro_nomeado_por_competencia(tmp_path):
    rec = recurso(
        id="ceap",
        url="https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip",
        publicacao="por_competencia",
        competencia={"tipo": "ano", "inicio": 2008},
        cadencia={"corrente": "diaria", "anteriores": "semanal"},
        formato={"tipo": "csv", "compressao": "zip", "arquivo": "Ano-{ano}.csv"},
    )
    original = tmp_path / "original.zip"
    original.write_bytes(zip_com({"leiame.txt": b"x", "Ano-2008.csv": CEAP_CSV.encode()}))
    preparado = arquivo.preparar(rec, Competencia.de_ano(2008), original, tmp_path)
    assert preparado.csv is not None and preparado.csv.read_bytes() == CEAP_CSV.encode()
    with pytest.raises(ErroColeta, match="Ano-2009.csv"):
        arquivo.preparar(rec, Competencia.de_ano(2009), original, tmp_path)


def test_zip_com_varios_membros_sem_formato_arquivo_falha(tmp_path):
    original = tmp_path / "original.zip"
    original.write_bytes(zip_com({"a.csv": b"1", "b.csv": b"2"}))
    with pytest.raises(ErroColeta, match="2 arquivos"):
        arquivo.preparar(recurso(), Competencia.de_dia(HOJE), original, tmp_path)


def test_preencher_marcadores():
    competencia = Competencia.de_dia(date(2026, 10, 2))
    assert preencher("x/{data}/{ano}/{legislatura}", competencia, date(2026, 10, 3)) == (
        "x/20261002/2026/57"
    )
    with pytest.raises(ErroColeta, match="marcador"):
        preencher("x/{desconhecido}", competencia, date(2026, 10, 3))


def test_extensao_a_partir_da_url_final():
    assert extensao_de("https://x/cotas/Ano-2025.csv.zip") == "csv.zip"
    assert extensao_de("https://x/saida/ceis/20261002_CEIS.zip?a=1") == "zip"
    assert extensao_de("https://x/download-de-dados/ceis/20261002") == "bin"


def test_arquivo_no_zip_por_curinga(tmp_path):
    from coletor.adaptadores.arquivo import preparar
    from coletor.competencias import Competencia

    original = tmp_path / "o.zip"
    original.write_bytes(
        zip_com(
            {
                "202404_ItemLicitação.csv": b"a\n1\n",
                "202404_Licitação.csv": b"a\n2\n",
                "202404_ParticipantesLicitação.csv": b"a\n3\n",
            }
        )
    )
    regra = recurso(
        formato={"tipo": "csv", "compressao": "zip", "arquivo": "{anomes}_Licita*o.csv"}
    )
    preparado = preparar(regra, Competencia.de_mes(2024, 4), original, tmp_path)
    assert preparado.csv.read_bytes() == b"a\n2\n"


def test_curinga_ambiguo_falha(tmp_path):
    from coletor.adaptadores.arquivo import preparar
    from coletor.adaptadores.base import ErroColeta
    from coletor.competencias import Competencia

    original = tmp_path / "o.zip"
    original.write_bytes(zip_com({"202404_A.csv": b"a\n", "202404_B.csv": b"b\n"}))
    regra = recurso(formato={"tipo": "csv", "compressao": "zip", "arquivo": "{anomes}_*.csv"})
    with pytest.raises(ErroColeta, match="2 arquivos"):
        preparar(regra, Competencia.de_mes(2024, 4), original, tmp_path)


def test_zip_acima_do_teto_e_recusado(tmp_path, monkeypatch):
    monkeypatch.setattr(arquivo, "LIMITE_DESCOMPACTADO", 10)
    rec = recurso(formato={"tipo": "csv", "compressao": "zip"})
    original = tmp_path / "original.zip"
    original.write_bytes(zip_com({"a.csv": b"x" * 11}))
    with pytest.raises(ErroColeta, match="excede o teto"):
        arquivo.preparar(rec, Competencia.de_ano(2026), original, tmp_path)
