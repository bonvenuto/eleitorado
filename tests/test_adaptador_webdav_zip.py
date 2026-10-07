import hashlib
import io
from datetime import date

import duckdb
import httpx
import pytest

from coletor.adaptadores import webdav_zip
from coletor.adaptadores.base import ErroColeta
from coletor.competencias import Competencia
from tests.amostras import RAIZ_WEBDAV, propfind_webdav, recurso_webdav, zip_com

HOJE = date(2026, 10, 6)


@pytest.fixture
def lago(tmp_path, monkeypatch):
    lago = tmp_path / "lago"
    (lago / "rfb").mkdir(parents=True)
    duckdb.sql(
        "copy (select * from (values ('11222333'), ('44555666')) t(raiz)) "
        f"to '{(lago / 'rfb' / 'raizes.parquet').as_posix()}' (format parquet)"
    )
    monkeypatch.setenv("ELEITORADO_LAGO", str(lago))
    return lago


def test_registro_com_quebra_de_linha_entre_aspas_continua():
    linhas = [b'"1";"a\n', b'b";"c"\n', b'"2";"d";"e"\n']
    assert list(webdav_zip.registros(linhas)) == [b'"1";"a\nb";"c"\n', b'"2";"d";"e"\n']


def test_recorte_mantem_as_raizes_le_latin1_e_tira_nul():
    fonte = (
        '"11222333";"AÇÚCAR LTDA";"01"\n"99999999";"OUTRA";"05"\n"44555666";"ZÉ\x00\x00 ME";"01"\n'
    ).encode("latin-1")
    saida = io.BytesIO()
    lidos, mantidos = webdav_zip.recortar(
        io.BytesIO(fonte), saida, frozenset({b"11222333", b"44555666"}), 3, "Empresas0.zip"
    )
    assert (lidos, mantidos) == (3, 2)
    assert saida.getvalue().decode("utf-8") == (
        '"11222333";"AÇÚCAR LTDA";"01"\n"44555666";"ZÉ ME";"01"\n'
    )


def test_byte_0x8f_solto_nao_derruba_o_recorte():
    saida = io.BytesIO()
    webdav_zip.recortar(io.BytesIO(b'"11222333";"\x8f";"01"\n'), saida, None, 3, "x.zip")
    assert saida.getvalue().decode("utf-8") == '"11222333";"\x8f";"01"\n'


def test_numero_de_colunas_diferente_do_layout_falha():
    with pytest.raises(ErroColeta, match="Empresas0.zip: 4 colunas, o layout tem 3"):
        webdav_zip.recortar(
            io.BytesIO(b'"1";"2";"3";"4"\n'), io.BytesIO(), None, 3, "Empresas0.zip"
        )


def test_competencia_disponivel_e_a_pasta_mais_recente(respx_mock, http):
    respx_mock.route(method="PROPFIND", url=RAIZ_WEBDAV).mock(
        return_value=httpx.Response(
            207,
            text=propfind_webdav(
                "/public.php/webdav/", [("2026-08/", None), ("2026-09/", None), ("x.txt", 1)]
            ),
        )
    )
    assert webdav_zip.competencia_disponivel(recurso_webdav(), http) == Competencia.de_mes(2026, 9)


def test_sem_pasta_de_competencia_falha_com_mensagem_clara(respx_mock, http):
    respx_mock.route(method="PROPFIND", url=RAIZ_WEBDAV).mock(
        return_value=httpx.Response(207, text=propfind_webdav("/public.php/webdav/", []))
    )
    with pytest.raises(ErroColeta, match="o link mudou"):
        webdav_zip.competencia_disponivel(recurso_webdav(), http)


def test_extrai_o_recorte_de_todos_os_zips_do_grupo(respx_mock, http, tmp_path, lago):
    pasta = f"{RAIZ_WEBDAV}2026-09/"
    zips = {
        "Empresas0.zip": zip_com({"K.EMPRECSV": b'"11222333";"A";"01"\n"77777777";"B";"05"\n'}),
        "Empresas1.zip": zip_com({"K.EMPRECSV": b'"44555666";"C";"03"\n'}),
    }
    listagem = [(nome, len(conteudo)) for nome, conteudo in zips.items()]
    respx_mock.route(method="PROPFIND", url=pasta).mock(
        return_value=httpx.Response(
            207,
            text=propfind_webdav("/public.php/webdav/2026-09/", [*listagem, ("Socios0.zip", 9)]),
        )
    )
    for nome, conteudo in zips.items():
        respx_mock.get(f"{pasta}{nome}").mock(return_value=httpx.Response(200, content=conteudo))
    extracao = webdav_zip.extrair(
        recurso_webdav(), Competencia.de_mes(2026, 9), tmp_path, http, HOJE
    )
    assert extracao.arquivo_original.read_text(encoding="utf-8") == (
        '"cnpj_basico";"razao_social";"porte"\n"11222333";"A";"01"\n"44555666";"C";"03"\n'
    )
    assert [a["nome"] for a in extracao.parametros["arquivos"]] == list(zips)
    assert extracao.parametros["arquivos"][0]["linhas_lidas"] == 2
    assert extracao.parametros["arquivos"][0]["linhas_mantidas"] == 1
    assert (
        extracao.parametros["arquivos"][0]["sha256"]
        == hashlib.sha256(zips["Empresas0.zip"]).hexdigest()
    )
    assert extracao.bytes_arquivo == sum(len(c) for c in zips.values())
    assert not list(tmp_path.glob("*.zip"))  # os ZIPs não ficam no disco


def test_tabela_de_apoio_vai_inteira(respx_mock, http, tmp_path):
    pasta = f"{RAIZ_WEBDAV}2026-09/"
    conteudo = zip_com({"F.K03200$Z.D60912.CNAECSV": b'"0111301";"Cultivo de arroz"\n'})
    respx_mock.route(method="PROPFIND", url=pasta).mock(
        return_value=httpx.Response(
            207, text=propfind_webdav("/public.php/webdav/2026-09/", [("Cnaes.zip", len(conteudo))])
        )
    )
    respx_mock.get(f"{pasta}Cnaes.zip").mock(return_value=httpx.Response(200, content=conteudo))
    recurso = recurso_webdav(raizes=None, arquivos="Cnaes.zip")
    recurso.recorte.colunas[:] = ["codigo", "descricao"]
    extracao = webdav_zip.extrair(recurso, Competencia.de_mes(2026, 9), tmp_path, http, HOJE)
    assert extracao.arquivo_original.read_text(encoding="utf-8").splitlines()[1] == (
        '"0111301";"Cultivo de arroz"'
    )


def test_sem_o_parquet_das_raizes_falha_antes_de_baixar(respx_mock, http, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEITORADO_LAGO", str(tmp_path / "vazio"))
    with pytest.raises(ErroColeta, match="int_rfb__raizes_interesse"):
        webdav_zip.extrair(recurso_webdav(), Competencia.de_mes(2026, 9), tmp_path, http, HOJE)
    assert not respx_mock.calls


def test_nenhum_zip_do_grupo_na_pasta_falha(respx_mock, http, tmp_path, lago):
    pasta = f"{RAIZ_WEBDAV}2026-09/"
    respx_mock.route(method="PROPFIND", url=pasta).mock(
        return_value=httpx.Response(207, text=propfind_webdav("/public.php/webdav/2026-09/", []))
    )
    with pytest.raises(ErroColeta, match="nenhum arquivo Empresas"):
        webdav_zip.extrair(recurso_webdav(), Competencia.de_mes(2026, 9), tmp_path, http, HOJE)
