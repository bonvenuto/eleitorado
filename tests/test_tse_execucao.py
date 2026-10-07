"""Execução fixada: trocar vigente ou acrescentar raw nunca altera o SQL selecionado."""

import hashlib
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest
from jinja2 import Environment

from coletor.esquemas import carregar_esquemas, garantir_fontes
from coletor.hashes import json_canonico
from tests.test_tse_selecao import montar_vetor


def preparar(*args, **kwargs):
    return importlib.import_module("coletor.tse.execucao").preparar_execucao_tse(*args, **kwargs)


def macro(nome, variaveis, lago, *args, target="prod"):
    def erro(mensagem):
        raise ValueError(mensagem)

    def consultar(sql):
        with duckdb.connect() as conexao:
            return SimpleNamespace(rows=conexao.execute(sql).fetchall())

    ambiente = Environment(extensions=["jinja2.ext.do"])
    modulo = ambiente.from_string(
        Path("dbt/macros/tse.sql").read_text(encoding="utf-8")
    ).make_module(
        {
            "execute": True,
            "run_query": consultar,
            "var": lambda chave, default=None: variaveis.get(chave, default),
            "env_var": lambda chave, default=None: str(lago).replace("\\", "/"),
            "target": SimpleNamespace(name=target),
            "exceptions": SimpleNamespace(raise_compiler_error=erro),
        }
    )
    return str(getattr(modulo, nome)(*args))


def ler_bens(execucao, lago):
    sql = macro("fonte_tse", execucao.vars_dbt, lago, "bens")
    with duckdb.connect() as conexao:
        return conexao.execute(f"select vr_bem_candidato from {sql}").fetchall()


def test_selecao_lida_uma_vez(tmp_path):
    lago, selecao = montar_vetor(tmp_path / "d'agua")
    vigente = lago / "estado/tse/vigente.json"
    vigente.write_text(
        json_canonico({"selecao_id": selecao.selecao_id, "versoes": selecao.versoes})
    )
    rejeitado = lago / "raw/tse/bens/2024/rejeitada/dados.parquet"
    rejeitado.parent.mkdir(parents=True)
    with duckdb.connect() as conexao:
        conexao.execute(
            "copy (select '999' vr_bem_candidato) to ? (format parquet)", [str(rejeitado)]
        )
    execucao = preparar(lago, "execucao-1", "prod")
    vigente.write_text("corrompido")
    assert ler_bens(execucao, lago) == [("100",)] * 4
    assert execucao.publicavel
    assert execucao.selecao_id == selecao.selecao_id
    assert list(execucao.saida.iterdir()) == []
    documento = json.loads((execucao.saida.parent / "preparacao.json").read_bytes())
    assert documento["vars"] == execucao.vars_dbt
    assert (
        documento["vars_digest"]
        == hashlib.sha256(json_canonico(execucao.vars_dbt).encode()).hexdigest()
    )
    assert documento["selecao"]["versoes"] == selecao.versoes
    assert documento["protocolo"] == "tse:preparacao:v1"
    assert documento["saida"] == "estado/tse/publicacoes/preparadas/execucao-1/marts"
    assert (
        macro("tse_saida_mart", execucao.vars_dbt, lago, "resumo")
        == (execucao.saida / "resumo.parquet").as_posix()
    )


def test_selecao_explicita_nao_le_vigente(tmp_path):
    lago, selecao = montar_vetor(tmp_path)
    (lago / "estado/tse/vigente.json").write_text("corrompido")
    execucao = preparar(lago, "candidato", "prod", selecao)
    assert ler_bens(execucao, lago) == [("100",)] * 4
    assert (lago / "estado/tse/vigente.json").read_text() == "corrompido"


def test_seletor_corrompido_nao_vira_vazio(tmp_path):
    lago, _ = montar_vetor(tmp_path)
    (lago / "estado/tse/vigente.json").write_text("corrompido")
    with pytest.raises(ValueError):
        preparar(lago, "invalida", "prod")
    assert not (lago / "estado/tse/publicacoes/preparadas/invalida").exists()


@pytest.mark.parametrize("parcial", [False, True])
def test_bootstrap_sem_marcador_nao_publica(tmp_path, parcial):
    lago = tmp_path / "lago"
    if parcial:
        raw = lago / "raw/tse/bens/2024/rejeitada/dados.parquet"
        raw.parent.mkdir(parents=True)
        raw.write_bytes(b"rejeitado")
    execucao = preparar(lago, "bootstrap", "prod")
    assert not execucao.publicavel
    assert execucao.selecao_id is None
    assert ler_bens(execucao, lago) == []
    assert not (lago / "raw/tse/bens/vazio").exists()


def test_marcador_sem_vigente_falha(tmp_path):
    marcador = tmp_path / "estado/tse/inicializado.json"
    marcador.parent.mkdir(parents=True)
    marcador.write_text('{"protocolo":"tse:inicializado:v1"}')
    with pytest.raises(ValueError):
        preparar(tmp_path, "ausente", "prod")


def test_recuperacao_bloqueia_antes_do_bootstrap(tmp_path):
    (tmp_path / "estado/tse/.recuperacao-incerta").mkdir(parents=True)
    with pytest.raises(OSError):
        preparar(tmp_path, "incerta", "prod")
    assert not (tmp_path / "estado/tse/publicacoes").exists()


def test_preparacao_exclusiva_nao_sobrescreve(tmp_path):
    execucao = preparar(tmp_path, "uma-vez", "ci")
    documento = execucao.saida.parent / "preparacao.json"
    original = documento.read_bytes()
    with pytest.raises(FileExistsError):
        preparar(tmp_path, "uma-vez", "ci")
    assert documento.read_bytes() == original


@pytest.mark.parametrize(
    "identidade", ["../fora", "a/b", "", ".", "a\\b", "com.ponto", "a" * 129, None]
)
def test_execucao_confinada(tmp_path, identidade):
    with pytest.raises(ValueError):
        preparar(tmp_path, identidade, "ci")


def test_garantir_fontes_nao_cria_raw_tse(tmp_path):
    garantir_fontes(tmp_path, {"raw/tse/bens": {"x": "VARCHAR"}})
    assert not (tmp_path / "raw/tse").exists()


def test_defaults_ci_tipados_privados(tmp_path):
    from scripts import lago_vazio

    esquemas = carregar_esquemas(Path("dbt"))
    lago_vazio.PASTA = tmp_path
    try:
        lago_vazio.gerar(esquemas)
    finally:
        lago_vazio.PASTA = Path("dbt/tests/lago_vazio").resolve()
    sql = macro("fonte_tse", {}, tmp_path, "bens", target="ci")
    with duckdb.connect() as conexao:
        assert conexao.execute(f"select count(*) from {sql}").fetchone() == (0,)
        colunas = dict(
            (r[0], r[1]) for r in conexao.execute(f"describe select * from {sql}").fetchall()
        )
    assert colunas["vr_bem_candidato"] == "VARCHAR"
    assert colunas["_competencia_data"] == "DATE"
    assert colunas["_linha"] == "BIGINT"
    assert colunas["ano_arquivo"] == "INTEGER"
    assert colunas["versao_id"] == "VARCHAR"
    assert colunas["layout_id"] == "VARCHAR"
    assert not (tmp_path / "raw/tse").exists()
    with pytest.raises(ValueError):
        macro("fonte_tse", {}, tmp_path, "bens")


@pytest.mark.parametrize("fontes", [{}, {"bens": []}, {"bens": ["raw/tse/**/*.parquet"]}])
def test_macro_recusa_fontes_nao_explicitas(tmp_path, fontes):
    with pytest.raises(ValueError):
        macro("fonte_tse", {"tse_fontes": fontes}, tmp_path, "bens")


def test_saida_mart_explicita_e_confinada(tmp_path):
    with pytest.raises(ValueError):
        macro("tse_saida_mart", {}, tmp_path, "resumo")
    with pytest.raises(ValueError):
        macro("tse_saida_mart", {"tse_saida": str(tmp_path)}, tmp_path, "../fora")


def test_macro_proveniencia_selecionada(tmp_path):
    lago, selecao = montar_vetor(tmp_path / "d'agua")
    execucao = preparar(lago, "proveniencia", "prod", selecao)
    sql = macro("fonte_tse", execucao.vars_dbt, lago, "bens")
    with duckdb.connect() as conexao:
        linhas = conexao.execute(
            f"select ano_arquivo, versao_id, layout_id from {sql} order by ano_arquivo"
        ).fetchall()
    assert [r[0] for r in linhas] == [2018, 2020, 2022, 2024]
    assert [r[1] for r in linhas] == [
        selecao.versoes[f"tse.bens:{a}"] for a in (2018, 2020, 2022, 2024)
    ]
    assert [r[2] for r in linhas] == [f"tse:bens:{a}:v1" for a in (2018, 2020, 2022, 2024)]


def test_macro_recusa_selecao_sem_proveniencia(tmp_path):
    with pytest.raises(ValueError, match="proveniência"):
        macro("fonte_tse", {"tse_fontes": {"bens": ["arquivo.parquet"]}}, tmp_path, "bens")


@pytest.mark.parametrize("alteracao", ["ausente", "ano", "versao", "layout", "extra"])
def test_macro_recusa_proveniencia_invalida(tmp_path, alteracao):
    arquivo = (tmp_path / "bens.parquet").as_posix()
    with duckdb.connect() as conexao:
        conexao.execute("copy (select '100' vr_bem_candidato) to ? (format parquet)", [arquivo])
    meta = {"ano_arquivo": 2024, "versao_id": "a" * 64, "layout_id": "tse:bens:2024:v1"}
    mapa = {arquivo: meta}
    if alteracao == "ausente":
        mapa = {}
    elif alteracao == "ano":
        meta["ano_arquivo"] = "2024"
    elif alteracao == "versao":
        meta["versao_id"] = "z" * 64
    elif alteracao == "layout":
        meta["layout_id"] = "tse:bens:2022:v1"
    else:
        mapa["arquivo-nao-selecionado.parquet"] = dict(meta)
    with pytest.raises(ValueError):
        macro(
            "fonte_tse",
            {"tse_fontes": {"bens": [arquivo]}, "tse_proveniencia": mapa},
            tmp_path,
            "bens",
        )


@pytest.mark.parametrize("reservado", ["ano_arquivo", "versao_id", "layout_id"])
def test_macro_recusa_colisao_raw_proveniencia(tmp_path, reservado):
    arquivo = (tmp_path / "colisao.parquet").as_posix()
    with duckdb.connect() as conexao:
        conexao.execute(
            f"copy (select null::varchar as {reservado}) to ? (format parquet)", [arquivo]
        )
    variaveis = {
        "tse_fontes": {"bens": [arquivo]},
        "tse_proveniencia": {
            arquivo: {"ano_arquivo": 2024, "versao_id": "a" * 64, "layout_id": "tse:bens:2024:v1"}
        },
    }
    with pytest.raises(ValueError, match="colide"):
        macro("fonte_tse", variaveis, tmp_path, "bens")


def test_contexto_bootstrap_so_vazio_conhecido(tmp_path):
    execucao = preparar(tmp_path, "bootstrap-contexto", "prod")
    assert execucao.vars_dbt["tse_contexto"] == {"selecao_id": None, "entradas_digest": None}
    sql = macro("tse_contexto_sql", execucao.vars_dbt, tmp_path)
    with duckdb.connect() as con:
        assert con.execute(sql).fetchall() == [(None, None)]
    for contexto in (None, {}, {"selecao_id": "a" * 64, "entradas_digest": None}):
        with pytest.raises(ValueError):
            macro("tse_contexto_sql", {**execucao.vars_dbt, "tse_contexto": contexto}, tmp_path)
    vars_reais = {**execucao.vars_dbt, "tse_fontes": {"bens": ["outro.parquet"]}}
    with pytest.raises(ValueError):
        macro("tse_contexto_sql", vars_reais, tmp_path)


def test_contexto_null_ci_explicito_confere_vazio(tmp_path):
    preparar(tmp_path, "bootstrap-ci", "ci")
    variaveis = {"tse_contexto": {"selecao_id": None, "entradas_digest": None}}
    assert "null::varchar" in macro("tse_contexto_sql", variaveis, tmp_path, target="ci")
    arquivo = tmp_path / "estado/tse/ci/bens/vazio/vazio.parquet"
    with duckdb.connect() as con:
        con.execute("copy (select 1 as dado) to ? (format parquet)", [str(arquivo)])
    with pytest.raises(ValueError, match="Bootstrap TSE exige arquivo vazio"):
        macro("tse_contexto_sql", variaveis, tmp_path, target="ci")
