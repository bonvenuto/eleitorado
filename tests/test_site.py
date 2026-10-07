"""`coletor site`: contrato (esquemas × exemplos) e gravação dos arquivos do site."""

import gzip
import json
from pathlib import Path

import duckdb
import pytest

from coletor.site import TIPOS, ErroSite, carregar_validadores, gerar_site, tipo_do_caminho
from tests.amostras import RAIZ

ESQUEMAS = RAIZ / "site" / "esquemas"
EXEMPLOS = RAIZ / "site" / "exemplos"


def _exemplos() -> dict[str, dict]:
    return {
        p.relative_to(EXEMPLOS).as_posix(): json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(EXEMPLOS.rglob("*.json"))
    }


def _banco(tmp_path: Path, arquivos: dict[str, object]) -> Path:
    banco = tmp_path / "eleitorado.duckdb"
    con = duckdb.connect(str(banco))
    con.execute(
        "create schema site; create table site.site_arquivos (caminho varchar, conteudo varchar)"
    )
    for caminho, documento in arquivos.items():
        conteudo = (
            documento if isinstance(documento, str) else json.dumps(documento, ensure_ascii=False)
        )
        con.execute("insert into site.site_arquivos values (?, ?)", [caminho, conteudo])
    con.close()
    return banco


def _ler(publico: Path, caminho: str) -> dict:
    return json.loads(gzip.decompress((publico / "site" / caminho).read_bytes()))


# ---- contrato: exemplos × esquemas


@pytest.mark.parametrize("caminho", sorted(_exemplos()))
def test_exemplo_segue_o_esquema(caminho):
    validadores = carregar_validadores(ESQUEMAS)
    documento = _exemplos()[caminho]
    erros = [e.message for e in validadores[tipo_do_caminho(caminho)].iter_errors(documento)]
    assert erros == []


def test_todo_tipo_de_arquivo_tem_exemplo():
    assert {tipo_do_caminho(c) for c in _exemplos()} == set(TIPOS)


def test_esquema_recusa_campo_que_nao_existe():
    validadores = carregar_validadores(ESQUEMAS)
    documento = _exemplos()["parlamentar/camara-900001.json"]
    documento["cota"]["inventado"] = 1
    assert list(validadores["parlamentar"].iter_errors(documento))


def test_esquema_aceita_cnpj_alfanumerico():
    validadores = carregar_validadores(ESQUEMAS)
    documento = _exemplos()["empresa/b_112.json"]
    documento["bloco"] = "1AB"
    documento["empresas"] = {"1AB2C3D4": documento["empresas"]["11222333"]}
    assert list(validadores["empresa"].iter_errors(documento)) == []


# ---- gerar_site


def test_grava_os_arquivos_em_gzip_deterministico(tmp_path):
    exemplos = _exemplos()
    banco = _banco(tmp_path, exemplos)
    publico = tmp_path / "publico"

    assert gerar_site(banco, publico, ESQUEMAS) == len(exemplos)
    primeiro = (publico / "site" / "resumo.json").read_bytes()
    assert _ler(publico, "resumo.json") == exemplos["resumo.json"]
    assert _ler(publico, "empresa/b_112.json") == exemplos["empresa/b_112.json"]

    gerar_site(banco, publico, ESQUEMAS)
    assert (publico / "site" / "resumo.json").read_bytes() == primeiro
    assert not (publico / "site.novo").exists()


def test_apaga_arquivo_que_deixou_de_existir(tmp_path):
    publico = tmp_path / "publico"
    antigo = publico / "site" / "empresa" / "999.json"
    antigo.parent.mkdir(parents=True)
    antigo.write_bytes(b"x")
    gerar_site(_banco(tmp_path, _exemplos()), publico, ESQUEMAS)
    assert not antigo.exists()


def test_cpf_completo_num_texto_impede_tudo_sem_mostrar_o_cpf(tmp_path):
    publico = tmp_path / "publico"
    (publico / "site").mkdir(parents=True)
    (publico / "site" / "resumo.json").write_bytes(b"anterior")
    arquivos = _exemplos()
    arquivos["busca/empresas/p_emp.json"]["empresas"][0]["nome"] = "JOSE DA SILVA 12345678909"

    with pytest.raises(ErroSite, match="busca/empresas/p_emp.json") as erro:
        gerar_site(_banco(tmp_path, arquivos), publico, ESQUEMAS)

    assert "12345678909" not in str(erro.value)
    assert (publico / "site" / "resumo.json").read_bytes() == b"anterior"
    assert not (publico / "site.novo").exists()


def test_valor_com_onze_digitos_e_chave_id_nao_sao_cpf(tmp_path):
    arquivos = _exemplos()
    arquivos["resumo.json"]["totais"]["contratos"] = 12345678901.23
    arquivos["resumo.json"]["alertas_recentes"][0]["alerta_id"] = "55915857505bc16506014ca3f3d755ec"
    gerar_site(_banco(tmp_path, arquivos), tmp_path / "publico", ESQUEMAS)


def test_arquivo_fora_do_esquema(tmp_path):
    arquivos = _exemplos()
    arquivos["resumo.json"]["inventado"] = True
    with pytest.raises(ErroSite, match=r"resumo.json: fora do esquema"):
        gerar_site(_banco(tmp_path, arquivos), tmp_path / "publico", ESQUEMAS)


@pytest.mark.parametrize("caminho", ["../fora.json", "parlamentar/../x.json", "/abs.json"])
def test_caminho_invalido(tmp_path, caminho):
    arquivos = _exemplos()
    arquivos[caminho] = arquivos["resumo.json"]
    with pytest.raises(ErroSite):
        gerar_site(_banco(tmp_path, arquivos), tmp_path / "publico", ESQUEMAS)


def test_arquivo_grande_demais(tmp_path):
    with pytest.raises(ErroSite, match="gzip"):
        gerar_site(_banco(tmp_path, _exemplos()), tmp_path / "publico", ESQUEMAS, limite_gzip=100)


def test_sem_resumo_falha(tmp_path):
    arquivos = _exemplos()
    del arquivos["resumo.json"]
    with pytest.raises(ErroSite, match="resumo"):
        gerar_site(_banco(tmp_path, arquivos), tmp_path / "publico", ESQUEMAS)


def test_sem_banco_falha(tmp_path):
    with pytest.raises(ErroSite, match="rode o dbt"):
        gerar_site(tmp_path / "nao_existe.duckdb", tmp_path / "publico", ESQUEMAS)


def test_bloco_de_cnpj_alfanumerico(tmp_path):
    arquivos = _exemplos()
    empresa = arquivos.pop("empresa/b_112.json")
    empresa["bloco"] = "1AB"
    empresa["empresas"] = {"1AB2C3D4": empresa["empresas"]["11222333"]}
    arquivos["empresa/b_1AB.json"] = empresa
    publico = tmp_path / "publico"
    gerar_site(_banco(tmp_path, arquivos), publico, ESQUEMAS)
    assert _ler(publico, "empresa/b_1AB.json")["bloco"] == "1AB"


# ---- comando `coletor site`


def test_comando_site_nao_precisa_de_credenciais(tmp_path):
    from coletor.cli import main

    lago = tmp_path / "lago"
    lago.mkdir()
    banco = _banco(tmp_path, _exemplos())
    banco.rename(lago / "ci.duckdb")
    publico = tmp_path / "publico"
    codigo = main(
        ["--target", "ci", "site", "--esquemas", str(ESQUEMAS)],
        env={"ELEITORADO_LAGO": str(lago), "ELEITORADO_PUBLICO": str(publico)},
    )
    assert codigo == 0
    assert _ler(publico, "resumo.json")["esquema"] == 1


def test_comando_site_com_erro_sai_com_1(tmp_path):
    from coletor.cli import main

    codigo = main(
        ["site", "--esquemas", str(ESQUEMAS)],
        env={"ELEITORADO_LAGO": str(tmp_path), "ELEITORADO_PUBLICO": str(tmp_path / "p")},
    )
    assert codigo == 1
