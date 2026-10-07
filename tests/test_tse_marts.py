"""Marts C2: isolamento físico, allowlists e identidade pública com SQL produtivo."""

import json
import os
import re
import shutil
import subprocess
from decimal import Decimal

import duckdb
import pytest
import yaml

from tests.amostras import RAIZ

MARTS = {
    "dim_candidatura": {
        "candidatura_id",
        "cd_eleicao",
        "sq_candidato",
        "data_eleicao",
        "cargo_codigo",
        "cargo",
        "uf_sigla",
        "localidade_codigo",
        "localidade",
        "nome_publico",
        "partido_numero",
        "partido_sigla",
        "situacao_eleitoral",
    },
    "fct_receita_campanha_resumo": {
        "candidatura_id",
        "natureza_recurso",
        "origem_recurso",
        "valor",
        "quantidade",
    },
    "fct_despesa_campanha_pj": {
        "despesa_id",
        "candidatura_id",
        "tipo_fato",
        "fornecedor_cnpj",
        "data",
        "valor",
    },
    "fct_patrimonio_declarado": {"candidatura_id", "tipo_bem_codigo", "quantidade", "valor"},
}


def _sql_linha(row):
    def literal(value):
        if value is None:
            return "null::varchar"
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, (int, Decimal)):
            return f"{value}::decimal(38,2)"
        return "'" + value.replace("'", "''") + "'::varchar"

    return "select " + ", ".join(
        f"{literal(v)}"
        + ("::date" if k in {"data", "data_eleicao", "data_prestacao"} else "")
        + f' as "{k}"'
        for k, v in row.items()
    )


@pytest.fixture(scope="module")
def marts_c2(tmp_path_factory):
    pasta = tmp_path_factory.mktemp("tse-marts")
    projeto = pasta / "dbt"
    modelos = projeto / "models"
    (modelos / "intermediate").mkdir(parents=True)
    (modelos / "marts").mkdir()
    (modelos / "staging").mkdir()
    shutil.copytree(RAIZ / "dbt/macros", projeto / "macros")
    shutil.copytree(RAIZ / "dbt/tests/generic", projeto / "tests/generic")
    esquema = yaml.safe_load((RAIZ / "dbt/models/marts/tse/tse.yml").read_text(encoding="utf-8"))
    (modelos / "marts/tse.yml").write_text(
        yaml.safe_dump({"version": 2, "models": esquema["models"]}), encoding="utf-8"
    )
    (projeto / "dbt_project.yml").write_text(
        "name: eleitorado\nversion: '1.0'\nconfig-version: 2\nprofile: eleitorado\n"
        "flags:\n  send_anonymous_usage_stats: false\nmodels:\n  eleitorado:\n"
        "    intermediate:\n      +schema: intermediate\n      +materialized: table\n"
        "    staging:\n      +schema: staging\n      +materialized: table\n"
        "    marts:\n      +schema: marts\n      +materialized: external\n",
        encoding="utf-8",
    )
    for nome in MARTS:
        shutil.copyfile(RAIZ / f"dbt/models/marts/tse/{nome}.sql", modelos / f"marts/{nome}.sql")
    for nome in ["int_tse__fornecedores_elegiveis", "int_tse__receitas_publicaveis"]:
        shutil.copyfile(
            RAIZ / f"dbt/models/intermediate/tse/{nome}.sql", modelos / f"intermediate/{nome}.sql"
        )
    chave = dict(
        cd_eleicao="1",
        sq_prestador_contas="2",
        sq_despesa="3",
        tipo_prestacao="Final",
        data_prestacao="2024-11-01",
    )
    contrato = dict(
        **chave,
        candidatura_id="tse:1:4",
        sq_candidato="4",
        fato_elegivel=True,
        candidatura_elegivel=True,
        prestacao_elegivel=True,
        origem_ambigua=False,
        prestacao_ambigua=False,
        metadados_incompletos=False,
        fornecedor_documento="11222333000181",
        fornecedor_documento_valido=True,
        cd_tipo_fornecedor="2",
        ds_tipo_fornecedor="PESSOA JURIDICA",
        sq_candidato_fornecedor=None,
        nr_partido_fornecedor=None,
        cd_esfera_part_fornecedor=None,
        sg_partido_fornecedor=None,
        cd_cargo_fornecedor=None,
        nm_partido_fornecedor=None,
        nr_cnpj_prestador_conta=None,
        ds_esfera_part_fornecedor=None,
        valor=Decimal("100"),
        data="2024-10-01",
        ds_despesa="segredo 52998224725",
        item_id="privado-a",
        linha_original='{"cpf":"52998224725"}',
        campo_futuro_sensivel="contato privado",
    )
    candidato = dict(
        candidatura_id="tse:1:4",
        cd_eleicao="1",
        sq_candidato="4",
        data_eleicao="2024-10-06",
        candidatura_elegivel=True,
        cd_cargo="6",
        ds_cargo="Deputado",
        sg_uf="SP",
        sg_ue="SP",
        nm_ue="Sao Paulo",
        nm_candidato="NOME 52998224725",
        nm_urna_candidato="NOME PUBLICO",
        nr_partido="99",
        sg_partido="ABC",
        ds_sit_tot_turno="ELEITO",
        cpf_candidato="52998224725",
        ds_email="privado@exemplo.invalid",
        campo_futuro_sensivel="telefone privado",
    )
    entradas = {
        "int_tse__candidaturas": [candidato],
        "int_tse__contratadas": [contrato, {**contrato, "item_id": "privado-b"}],
        "int_tse__pagamentos": [{**contrato, "valor": Decimal("50"), "item_id": "parcela"}],
        "int_tse__receitas": [
            {
                "candidatura_id": "tse:1:4",
                "cd_eleicao": "1",
                "sq_prestador_contas": "2",
                "tipo_prestacao": "Final",
                "data_prestacao": "2024-11-01",
                "valor": Decimal("10"),
                "data": "2024-10-01",
                "fato_elegivel": True,
                "candidatura_elegivel": True,
                "prestacao_elegivel": True,
                "prestacao_ambigua": False,
                "origem_ambigua": False,
                "metadados_incompletos": False,
                "nr_cpf_cnpj_doador": "52998224725",
                "nr_cpf_cnpj_doador_valido": True,
                "cd_fonte_receita": "1",
                "ds_fonte_receita": "OUTROS RECURSOS",
                "cd_origem_receita": "10010200",
                "ds_origem_receita": "Recursos de pessoas físicas",
                "ds_natureza_receita": "FINANCEIRO",
                "ds_receita": "banco privado",
                "nr_cnpj_prestador_conta": None,
                "cd_esfera_partidaria_doador": None,
                "ds_esfera_partidaria_doador": None,
                "nr_partido_doador": None,
                "sg_partido_doador": None,
                "nm_partido_doador": None,
                "sq_candidato_doador": None,
                "cd_cargo_candidato_doador": None,
                "nr_candidato_doador": None,
            }
        ],
        "stg_tse__doador_originario": [
            {
                "cd_eleicao": "99",
                "sq_prestador_contas": "99",
                "tipo_prestacao": "Final",
                "data_prestacao": "2024-11-01",
            }
        ],
        "int_tse__patrimonio": [
            {
                "candidatura_id": "tse:1:4",
                "declaracao_efetiva": True,
                "patrimonio": Decimal("10"),
                "pessoa_id": "pessoa:52998224725",
            }
        ],
        "stg_tse__bens": [
            {
                "candidatura_id": "tse:1:4",
                "cd_tipo_bem_candidato": "11",
                "vr_bem_candidato": Decimal("10"),
                "ds_bem_candidato": "conta privada 52998224725",
            }
        ],
    }
    fundo = {
        **entradas["int_tse__receitas"][0],
        "nr_cpf_cnpj_doador": "12345678000195",
        "valor": Decimal("100"),
        "cd_fonte_receita": "0",
        "ds_fonte_receita": "FUNDO PARTIDARIO",
        "cd_origem_receita": "10020000",
        "ds_origem_receita": "Recursos de partido político",
        "cd_esfera_partidaria_doador": "N",
        "ds_esfera_partidaria_doador": "Nacional",
        "nr_partido_doador": "99",
        "sg_partido_doador": "ABC",
        "nm_partido_doador": "ABC",
    }
    entradas["int_tse__receitas"].append(fundo)
    for nome, linhas in entradas.items():
        camada = "staging" if nome.startswith("stg_") else "intermediate"
        (modelos / camada / f"{nome}.sql").write_text(
            "\nunion all\n".join(_sql_linha(row) for row in linhas), encoding="utf-8"
        )
    lago = pasta / "lago"
    lago.mkdir()
    legado = pasta / "publico-legado"
    saida = pasta / "saida-c2"
    saida.mkdir()
    (legado / "marts").mkdir(parents=True)
    resultado = subprocess.run(
        [
            "dbt",
            "build",
            "--project-dir",
            str(projeto),
            "--profiles-dir",
            str(RAIZ / "dbt"),
            "--target",
            "ci",
            "--vars",
            json.dumps({"tse_saida": saida.as_posix()}),
        ],
        env={
            **os.environ,
            "ELEITORADO_LAGO": lago.as_posix(),
            "ELEITORADO_PUBLICO": legado.as_posix(),
            "PYTHONIOENCODING": "utf-8",
        },
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    manifest = json.loads((projeto / "target/manifest.json").read_text(encoding="utf-8"))
    return pasta, projeto, lago, legado, saida, manifest


def test_saida_c2_isolada(marts_c2):
    _, projeto, _, legado, saida, manifest = marts_c2
    for nome in MARTS:
        config = manifest["nodes"][f"model.eleitorado.{nome}"]["config"]
        assert config.get("location") == (saida / f"{nome}.parquet").as_posix()
        assert (saida / f"{nome}.parquet").is_file()
        sql = (projeto / f"target/run/eleitorado/models/marts/{nome}.sql").read_text(
            encoding="utf-8"
        )
        assert saida.as_posix() in sql
        assert legado.as_posix() not in sql
    assert not list(legado.rglob("*.parquet"))


def test_novo_campo_sensivel_nao_vaza(marts_c2):
    _, _, _, legado, saida, _ = marts_c2
    with duckdb.connect() as con:
        for nome, permitidas in MARTS.items():
            caminho = saida / f"{nome}.parquet"
            if not caminho.exists():
                caminho = legado / "marts" / f"{nome}.parquet"
            colunas = con.execute(
                "describe select * from read_parquet(?)", [str(caminho)]
            ).fetchall()
            assert {c[0] for c in colunas} == permitidas
            for linha in con.execute("select * from read_parquet(?)", [str(caminho)]).fetchall():
                for valor in linha:
                    if isinstance(valor, str):
                        assert not re.search(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)", valor)


def test_ids_publicos_independem_conteudo_privado(marts_c2):
    _, projeto, lago, _, _, _ = marts_c2
    sql = (
        projeto / "target/compiled/eleitorado/models/marts/fct_despesa_campanha_pj.sql"
    ).read_text(encoding="utf-8")
    with duckdb.connect(str(lago / "ci.duckdb")) as con:
        antes = con.execute(sql).fetchall()
        assert len(antes) == 3
        for nome in ["int_tse__contratadas", "int_tse__pagamentos"]:
            con.execute(
                f"update intermediate.{nome} set item_id='outro', "
                "ds_despesa='outro segredo', linha_original='outro original', "
                "campo_futuro_sensivel='outro contato'"
            )
        depois = con.execute(sql).fetchall()
        assert sorted(antes) == sorted(depois)


def test_correcao_pf_nao_altera_marts(marts_c2):
    _, projeto, lago, _, _, _ = marts_c2
    pasta = projeto / "target/compiled/eleitorado/models"
    sqls = {nome: (pasta / f"marts/{nome}.sql").read_text(encoding="utf-8") for nome in MARTS}
    with duckdb.connect(str(lago / "ci.duckdb")) as con:
        antes = {nome: con.execute(sql).fetchall() for nome, sql in sqls.items()}
        assert antes["fct_receita_campanha_resumo"] == [
            ("tse:1:4", "financeiro", "fundo_partidario", Decimal("100"), 1)
        ]
        con.execute(
            "update intermediate.int_tse__receitas "
            "set valor=11, nr_cpf_cnpj_doador='12345678909' where cd_origem_receita='10010200'"
        )
        for nome in ["int_tse__receitas_publicaveis", "int_tse__fornecedores_elegiveis"]:
            sql = (pasta / f"intermediate/{nome}.sql").read_text(encoding="utf-8")
            con.execute(f"create or replace table intermediate.{nome} as " + sql)
        depois = {nome: con.execute(sql).fetchall() for nome, sql in sqls.items()}
        assert {n: sorted(v) for n, v in antes.items()} == {n: sorted(v) for n, v in depois.items()}
