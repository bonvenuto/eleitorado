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


class DbtFalso:
    def __init__(self, status: str = "sucesso") -> None:
        self.status = status
        self.chamadas: list[tuple[str, list[str]]] = []
        self.ambientes = []

    def __call__(self, diretorio, target, publico, argumentos=()):
        import os

        from coletor.dbt import ResultadoDbt

        self.ambientes.append(
            (os.environ.get("ELEITORADO_LAGO"), os.environ.get("ELEITORADO_PUBLICO"))
        )
        self.chamadas.append((target, list(argumentos)))
        return ResultadoDbt(self.status, 0)


def _comando_site(tmp_path: Path, dbt: DbtFalso, com_banco: bool = True) -> tuple[int, Path]:
    from coletor.cli import main

    lago = tmp_path / "lago"
    lago.mkdir()
    if com_banco:
        _banco(tmp_path, _exemplos()).rename(lago / "ci.duckdb")
    publico = tmp_path / "publico"
    codigo = main(
        ["--target", "ci", "site", "--esquemas", str(ESQUEMAS)],
        env={"ELEITORADO_LAGO": str(lago), "ELEITORADO_PUBLICO": str(publico)},
        dbt=dbt,
    )
    return codigo, publico


def test_comando_site_roda_o_dbt_do_site_e_grava_sem_credenciais(tmp_path):
    dbt = DbtFalso()
    codigo, publico = _comando_site(tmp_path, dbt)
    assert codigo == 0
    # os modelos do site rodam aqui, não no dbt build do pipeline (não bloqueiam os marts)
    [(target, argumentos)] = dbt.chamadas
    assert target == "ci"
    assert dbt.ambientes == [((tmp_path / "lago").as_posix(), publico.as_posix())]
    assert argumentos[:3] == ["--select", "path:models/site", "site_alerta_tipos"]
    variaveis = json.loads(argumentos[argumentos.index("--vars") + 1])
    assert set(variaveis) == {"tse_contexto", "tse_fontes", "tse_proveniencia", "tse_saida"}
    assert variaveis["tse_contexto"] == {"selecao_id": None, "entradas_digest": None}
    saida = Path(variaveis["tse_saida"])
    assert saida.is_relative_to(tmp_path / "lago/estado/tse/publicacoes/preparadas")
    assert Path(argumentos[-1]) == saida.parent / "dbt-target"
    assert not (saida.parent / "recibo.json").exists()
    assert not (tmp_path / "lago/estado/tse/vigente.json").exists()
    assert _ler(publico, "resumo.json")["esquema"] == 1


def test_comando_site_com_dbt_falhando_sai_com_1_sem_gravar(tmp_path):
    codigo, publico = _comando_site(tmp_path, DbtFalso("falha"))
    assert codigo == 1
    assert not (publico / "site").exists()


def test_comando_site_com_erro_sai_com_1(tmp_path):
    codigo, _ = _comando_site(tmp_path, DbtFalso(), com_banco=False)
    assert codigo == 1


def test_site_vigente_passa_vars_integrais_uma_vez_e_restaura_ambiente(tmp_path, monkeypatch):
    import os
    from dataclasses import asdict

    from coletor.cli import main
    from coletor.tse import execucao
    from tests.test_tse_selecao import montar_vetor

    lago, selecao = montar_vetor(tmp_path)
    vigente = lago / "estado/tse/vigente.json"
    vigente.write_text(json.dumps(asdict(selecao)), encoding="utf-8")
    anterior = vigente.read_bytes()
    chamadas = []
    preparar = execucao.preparar_execucao_tse

    def capturar(*args, **kwargs):
        preparada = preparar(*args, **kwargs)
        chamadas.append(preparada)
        return preparada

    monkeypatch.setattr(execucao, "preparar_execucao_tse", capturar)
    monkeypatch.setattr("coletor.site.gerar_site", lambda *a: 0)
    monkeypatch.setenv("ELEITORADO_LAGO", "anterior-relativo")
    monkeypatch.delenv("ELEITORADO_PUBLICO", raising=False)
    dbt = DbtFalso()
    publico = tmp_path / "publico"
    assert (
        main(
            ["--target", "ci", "site"],
            env={"ELEITORADO_LAGO": str(lago), "ELEITORADO_PUBLICO": str(publico)},
            dbt=dbt,
            fabrica=lambda c: pytest.fail("site nao monta GCP"),
        )
        == 0
    )
    [preparada] = chamadas
    argumentos = dbt.chamadas[0][1]
    assert json.loads(argumentos[argumentos.index("--vars") + 1]) == preparada.vars_dbt
    assert preparada.vars_dbt["tse_contexto"]["selecao_id"] == selecao.selecao_id
    assert dbt.ambientes == [(lago.as_posix(), publico.as_posix())]
    assert os.environ["ELEITORADO_LAGO"] == "anterior-relativo"
    assert "ELEITORADO_PUBLICO" not in os.environ
    assert vigente.read_bytes() == anterior
    assert not (preparada.saida.parent / "recibo.json").exists()
