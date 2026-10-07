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
from jinja2 import Environment, nodes

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
    "monitor_tse": {
        "cobertura",
        "auditoria",
        "selecao_id",
        "entradas_id",
        "ano_arquivo",
        "layout_id",
        "prazo_dias",
        "familia",
        "rechecado_em",
        "versao_id",
    },
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
        + (
            "::date"
            if k
            in {
                "data",
                "data_eleicao",
                "data_prestacao",
                "data_emissao",
                "data_documento",
                "data_assinatura",
            }
            else ""
        )
        + ("::integer" if k == "ano_arquivo" else "")
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
    for nome in [
        "int_tse__fornecedores_elegiveis",
        "int_tse__receitas_publicaveis",
        "int_tse__cruzamentos",
    ]:
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
        ano_arquivo=2024,
        versao_id="a" * 64,
        layout_id="tse:contratadas:2024:v1",
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
    # Um fato de cada fonte C1. Evidências repetidas não podem expandir a cota.
    entradas.update(
        {
            "int_tse__vinculos_parlamentares": [
                dict(candidatura_id="tse:1:4", parlamentar_id="camara:1", estado="confirmado")
            ]
            * 2,
            "fct_despesa_cota_parlamentar": [
                dict(
                    despesa_id="cota-1",
                    parlamentar_id="camara:1",
                    fornecedor_tipo_documento="CNPJ",
                    fornecedor_documento_valido=True,
                    fornecedor_cnpj_raiz="11222333",
                    data_emissao="2024-10-02",
                    data_emissao_valida=True,
                    valor_reembolsado=Decimal("20"),
                    _coleta_id="c1-cota",
                )
            ],
            "int_cgu__emendas_pagamentos": [
                dict(
                    pagamento_linha_id="emenda-1",
                    autor_codigo="autor",
                    fase_despesa="Pagamento",
                    favorecido_tipo_documento="CNPJ",
                    favorecido_documento_valido=True,
                    favorecido_cnpj_raiz="11222333",
                    data_documento="2024-10-03",
                    valor_pago=Decimal("30"),
                    _coleta_id="c1-emenda",
                )
            ],
            "dim_autor_emenda": [dict(autor_codigo="autor", parlamentar_id="camara:1")],
            "fct_contrato_federal": [
                dict(
                    contrato_id="contrato-1",
                    fornecedor_tipo_documento="CNPJ",
                    fornecedor_documento_valido=True,
                    fornecedor_cnpj_raiz="11222333",
                    data_assinatura="2024-10-04",
                    valor_final=Decimal("40"),
                    valor_suspeito=False,
                    _coleta_id="c1-contrato",
                )
            ],
            "int_rfb__empresas": [dict(cnpj_raiz="outra", competencia_receita="2024-10")],
            "stg_meta__coletas": [
                dict(
                    coleta_id="coleta-selecionada",
                    orgao="tse",
                    recurso="contas",
                    competencia="2024",
                    status="carregada",
                    finalizada_em="2024-10-01T00:00:00",
                    sha256_arquivo="a" * 64,
                ),
                dict(
                    coleta_id="rechecagem",
                    orgao="tse",
                    recurso="contas",
                    competencia="2024",
                    status="sem_alteracao",
                    finalizada_em="2024-11-01T00:00:00",
                    sha256_arquivo="a" * 64,
                ),
                dict(
                    coleta_id="candidata-rejeitada",
                    orgao="tse",
                    recurso="contas",
                    competencia="2024",
                    status="carregada",
                    finalizada_em="2024-12-01T00:00:00",
                    sha256_arquivo="b" * 64,
                ),
            ],
        }
    )
    familias = [
        "candidaturas",
        "bens",
        "receitas",
        "contratadas",
        "pagamentos",
        "doador_originario",
    ]
    for familia in familias:
        entrada = "stg_tse__" + familia
        linhas = entradas.setdefault(entrada, [{}])
        for linha in linhas:
            linha.update(
                ano_arquivo=2024,
                versao_id="a" * 64,
                layout_id=f"tse:{familia}:2024:v1",
                _coleta_id="coleta-selecionada",
            )
    for nome, campo in [
        ("int_cota__despesas", "fornecedor_cnpj_raiz"),
        ("int_contratos_federais", "fornecedor_cnpj_raiz"),
        ("int_cgu__licitacao_participantes", "participante_cnpj_raiz"),
    ]:
        entradas[nome] = [{campo: "87654321"}]
    entradas["stg_cgu__emendas_favorecidos"] = [
        dict(favorecido_tipo_documento="CNPJ", favorecido_documento="87654321000199")
    ]
    entradas["int_cgu__sancoes_eventos"] = [dict(documento="87654321000199")]
    shutil.copyfile(
        RAIZ / "dbt/models/intermediate/int_rfb__raizes_interesse.sql",
        modelos / "intermediate/int_rfb__raizes_interesse.sql",
    )
    for nome, linhas in entradas.items():
        camada = "staging" if nome.startswith("stg_") else "intermediate"
        (modelos / camada / f"{nome}.sql").write_text(
            "\nunion all\n".join(_sql_linha(row) for row in linhas), encoding="utf-8"
        )
    lago = pasta / "lago"
    lago.mkdir()
    (lago / "estado").mkdir()
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
            json.dumps(
                {
                    "tse_saida": saida.as_posix(),
                    "tse_contexto": {
                        "selecao_id": "a" * 64,
                        "entradas_digest": "a12345678901" + "b" * 52,
                    },
                    "tse_fontes": {f: [f + ".parquet"] for f in familias},
                    "tse_proveniencia": {
                        f + ".parquet": {
                            "ano_arquivo": 2024,
                            "versao_id": "a" * 64,
                            "layout_id": f"tse:{f}:2024:v1",
                        }
                        for f in familias
                    },
                }
            ),
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
                for indice, valor in enumerate(linha):
                    if isinstance(valor, str) and not colunas[indice][0].endswith("_id"):
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


def _cruzamentos(marts_c2, con):
    _, projeto, _, _, _, _ = marts_c2
    sql = (
        projeto / "target/compiled/eleitorado/models/intermediate/int_tse__cruzamentos.sql"
    ).read_text(encoding="utf-8")
    cursor = con.execute(sql)
    colunas = [c[0] for c in cursor.description]
    return [dict(zip(colunas, row, strict=True)) for row in cursor.fetchall()]


def test_data_anterior_nao_cruza(marts_c2):
    with duckdb.connect(str(marts_c2[2] / "ci.duckdb")) as con:
        antes = _cruzamentos(marts_c2, con)
        assert len(antes) == 9  # três fatos TSE x três contextos C1; ponte duplicada não expande
        con.execute("begin")
        try:
            con.execute(
                "update intermediate.fct_despesa_cota_parlamentar "
                "set data_emissao=date '2024-09-30'"
            )
            con.execute(
                "update intermediate.fct_contrato_federal set data_assinatura=date '2024-10-01'"
            )
            assert {r["origem_c1"] for r in _cruzamentos(marts_c2, con)} == {"emenda_pagamento"}
        finally:
            con.execute("rollback")


def test_fato_invalido_nao_cruza(marts_c2):
    with duckdb.connect(str(marts_c2[2] / "ci.duckdb")) as con:
        con.execute("begin")
        try:
            con.execute(
                "update intermediate.fct_despesa_cota_parlamentar set data_emissao_valida=false"
            )
            con.execute("update intermediate.fct_contrato_federal set valor_suspeito=true")
            assert {r["origem_c1"] for r in _cruzamentos(marts_c2, con)} == {"emenda_pagamento"}
            con.execute("update intermediate.int_tse__contratadas set fato_elegivel=false")
            con.execute("update intermediate.int_tse__pagamentos set valor=null")
            assert _cruzamentos(marts_c2, con) == []
        finally:
            con.execute("rollback")


def test_emenda_so_pagamento_e_autoria_contextual(marts_c2):
    with duckdb.connect(str(marts_c2[2] / "ci.duckdb")) as con:
        linhas = _cruzamentos(marts_c2, con)
        assert {r["estado_autoria"] for r in linhas if r["origem_c1"] == "emenda_pagamento"} == {
            "autoria_contextual_nome"
        }
        assert all(r["parlamentar_id"] is None for r in linhas if r["origem_c1"] == "contrato")
        con.execute("begin")
        try:
            con.execute(
                "update intermediate.int_cgu__emendas_pagamentos set fase_despesa='Empenho'"
            )
            con.execute("delete from intermediate.int_tse__vinculos_parlamentares")
            restantes = _cruzamentos(marts_c2, con)
            assert len(restantes) == 3 and {r["origem_c1"] for r in restantes} == {"contrato"}
            assert {r["estado_autoria"] for r in restantes} == {"sem_autoria_demonstrada"}
        finally:
            con.execute("rollback")


def test_receita_ausente_cobertura_pendente(marts_c2):
    with duckdb.connect(str(marts_c2[2] / "ci.duckdb")) as con:
        linhas = _cruzamentos(marts_c2, con)
        assert {r["cobertura_receita"] for r in linhas} == {"cobertura_pendente"}
        assert all(r["competencia_receita"] is None for r in linhas)
        assert all(r["snapshot_legado_nao_atomico"] for r in linhas)
        assert {r["coleta_c1_id"] for r in linhas} == {"c1-cota", "c1-emenda", "c1-contrato"}


def test_monitor_vinculo_sem_relogio_e_lgpd(marts_c2):
    _, projeto, lago, _, saida, _ = marts_c2
    with duckdb.connect(str(lago / "ci.duckdb")) as con:
        rows = con.execute(
            "select familia, rechecado_em, cobertura, entradas_id "
            "from read_parquet(?) order by familia",
            [str(saida / "monitor_tse.parquet")],
        ).fetchall()
        assert len(rows) == 6
        for familia, instante, cobertura, hash_id in rows:
            assert "12345678901" in hash_id
            if familia in {"receitas", "contratadas", "pagamentos", "doador_originario"}:
                assert str(instante).startswith("2024-11-01") and cobertura == "vinculada"
            else:
                assert instante is None and cobertura == "pendente"
        sql = (projeto / "target/compiled/eleitorado/models/marts/monitor_tse.sql").read_text(
            encoding="utf-8"
        )
        assert not any(
            x in sql.lower() for x in ["current_timestamp", "current_date", "uuid", "edicao_id"]
        )
        antes = con.execute(sql).fetchall()
        assert antes == sorted(antes, key=lambda r: (r[2], r[3], r[4], r[5]))
        assert antes == con.execute(sql).fetchall()
        teste = next(
            (projeto / "target/compiled/eleitorado/models/marts/tse.yml").glob(
                "sem_cpf_completo_monitor_tse_*.sql"
            )
        )
        assert con.execute(teste.read_text(encoding="utf-8")).fetchall() == []
        con.execute(
            "create or replace view marts.monitor_tse as "
            "select * replace ('CPF 52998224725' as cobertura) from (" + sql + ")"
        )
        assert con.execute(teste.read_text(encoding="utf-8")).fetchall()


def test_raiz_tse_sem_ativar_alertas_c1(marts_c2):
    _, projeto, lago, _, _, manifest = marts_c2
    sql = (
        projeto / "target/compiled/eleitorado/models/intermediate/int_rfb__raizes_interesse.sql"
    ).read_text(encoding="utf-8")
    with duckdb.connect(str(lago / "ci.duckdb")) as con:
        origens = dict(con.execute(sql).fetchall())["11222333"]
        assert "tse_contratacao" in origens and "tse_pagamento" in origens
    macro = (RAIZ / "dbt/macros/rfb.sql").read_text(encoding="utf-8")
    arvore = Environment().parse(macro)
    funcao = next(n for n in arvore.find_all(nodes.Macro) if n.name == "rfb_fatos")
    referencias = {
        chamada.args[0].value
        for chamada in funcao.find_all(nodes.Call)
        if isinstance(chamada.node, nodes.Name) and chamada.node.name == "ref"
    }
    assert referencias == {
        "fct_despesa_cota_parlamentar",
        "fct_emenda_pagamento",
        "dim_autor_emenda",
        "fct_contrato_federal",
    }
    assert (
        "model.eleitorado.int_tse__cruzamentos"
        not in manifest["nodes"]["model.eleitorado.int_rfb__raizes_interesse"]["depends_on"][
            "nodes"
        ]
    )


def test_monitor_hash_malformado_cobertura_pendente(marts_c2):
    _, projeto, lago, _, _, _ = marts_c2
    sql = (projeto / "target/compiled/eleitorado/models/marts/monitor_tse.sql").read_text(
        encoding="utf-8"
    )
    with duckdb.connect(str(lago / "ci.duckdb")) as con:
        con.execute("begin")
        try:
            con.execute(
                "update staging.stg_meta__coletas set sha256_arquivo='sem-hash' "
                "where sha256_arquivo='" + "a" * 64 + "'"
            )
            cursor = con.execute(sql)
            rows = [
                dict(zip([c[0] for c in cursor.description], r, strict=True))
                for r in cursor.fetchall()
            ]
            assert all(r["rechecado_em"] is None and r["cobertura"] == "pendente" for r in rows)
        finally:
            con.execute("rollback")
