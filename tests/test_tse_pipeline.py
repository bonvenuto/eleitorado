"""Controlador TSE: evidencias frescas, falhas conservadoras e selecao explicita."""

import json
import uuid
from dataclasses import replace
from datetime import date
from functools import partial

import pytest
import yaml

from coletor.agenda import INTERVALO_DIAS, tarefas_pendentes
from coletor.dbt import ResultadoDbt, rodar_dbt
from coletor.manifesto import Orgao, RecursoCompleto
from coletor.meta import HistoricoColetas
from coletor.tse.selecao import conferir_recibo_tse, digest_entradas
from coletor.tse.validacoes import gravar_avaliacao
from tests.amostras import RAIZ
from tests.test_tse_selecao import montar_vetor


@pytest.fixture
def candidato(tmp_path):
    return montar_vetor(tmp_path)


def test_fonte_tse_tres_zips_quatro_anos():
    orgao = Orgao.model_validate(yaml.safe_load((RAIZ / "fontes/tse.yaml").read_text("utf-8")))
    recursos = [RecursoCompleto(orgao.orgao, r) for r in orgao.recursos]
    from tests.amostras_tse import recurso_tse

    assert len(recursos) == 3
    assert all(
        r.recurso.url == recurso_tse(r.recurso.id).url
        and r.recurso.familias == recurso_tse(r.recurso.id).familias
        for r in recursos
    )
    assert {f for r in recursos for f in r.recurso.familias} == {
        "candidaturas",
        "bens",
        "receitas",
        "contratadas",
        "pagamentos",
        "doador_originario",
    }
    assert all(r.recurso.grupo == "tse" for r in recursos)
    assert not [r for r in recursos if r.recurso.grupo == "diario"]
    assert INTERVALO_DIAS["mensal"] == 30
    assert all(
        r.recurso.cadencia.corrente == r.recurso.cadencia.anteriores == "mensal" for r in recursos
    )
    tarefas = tarefas_pendentes(recursos, HistoricoColetas(), date(2026, 10, 7))
    assert len(tarefas) == 12
    assert {t.competencia.rotulo for t in tarefas} == {"2018", "2020", "2022", "2024"}


def controlador(*args, **kwargs):
    from coletor.tse.pipeline import preparar_e_promover_tse

    return preparar_e_promover_tse(*args, **kwargs)


def executor_sintetico(status="pass", *, defeito=None, chamadas=None):
    def rodar(*, target, publico, argumentos, capturar):
        comando = [
            "dbt",
            "build",
            "--exclude-resource-type",
            "unit_test",
            *argumentos,
            "--project-dir",
            "dbt",
            "--profiles-dir",
            "dbt",
            "--target",
            target,
        ]
        if chamadas is not None:
            chamadas.append(comando)
        pasta = __import__("pathlib").Path(argumentos[argumentos.index("--target-path") + 1])
        pasta.mkdir(parents=True)
        saida = json.loads(argumentos[argumentos.index("--vars") + 1])["tse_saida"]
        __import__("pathlib").Path(saida, "resumo.parquet").write_bytes(b"saida sintetica")
        invocacao = str(uuid.uuid4())
        manifest = {
            "metadata": {"invocation_id": invocacao},
            "nodes": {
                "model.eleitorado.a": {"resource_type": "model"},
                "test.eleitorado.a": {"resource_type": "test"},
                "model.eleitorado.site_arquivos": {"resource_type": "model"},
                "seed.eleitorado.site_alerta_tipos": {"resource_type": "seed"},
            },
            "unit_tests": {},
        }
        resultados = {
            "metadata": {"invocation_id": invocacao},
            "args": {
                "which": "build",
                "target": target,
                "vars": json.loads(argumentos[argumentos.index("--vars") + 1]),
                "exclude_resource_types": ["unit_test"],
                "target_path": str(pasta),
                "project_dir": "dbt",
                "profiles_dir": "dbt",
            },
            "results": [
                {"unique_id": "model.eleitorado.a", "status": "success"},
                {"unique_id": "test.eleitorado.a", "status": status},
                {"unique_id": "model.eleitorado.site_arquivos", "status": "success"},
                {"unique_id": "seed.eleitorado.site_alerta_tipos", "status": "success"},
            ],
        }
        if defeito == "cobertura":
            resultados["results"].pop(0)
        if defeito in {"sem_site", "sem_seed"}:
            indice = 2 if defeito == "sem_site" else 3
            resultados["results"].pop(indice)
        if defeito == "site_falha":
            resultados["results"][2]["status"] = "error"
        if defeito == "exclude_site":
            comando.extend(["--exclude", "path:models/site", "site_alerta_tipos"])
        if defeito == "invocacao":
            resultados["metadata"]["invocation_id"] = str(uuid.uuid4())
        if defeito == "args":
            resultados["args"]["select"] = ["a"]
        if defeito == "target_path":
            resultados["args"]["target_path"] = "outra-execucao"
        if defeito != "sem_artefatos":
            for nome, conteudo in [("manifest", manifest), ("run_results", resultados)]:
                (pasta / f"{nome}.json").write_text(json.dumps(conteudo), encoding="utf-8")
        retorno = 0 if status == "pass" else 1
        capturar(comando, retorno, pasta)
        return ResultadoDbt("sucesso" if retorno == 0 else "falha", int(status == "fail"))

    return rodar


def test_pipeline_tse_falha_preserva_edicao(candidato):
    lago, selecao = candidato
    estado = lago / "estado/tse"
    (estado / "vigente.json").write_bytes(b"selecao anterior")
    manifesto = estado / "manifesto-anterior.json"
    manifesto.write_bytes(b"manifesto anterior")
    with pytest.raises(ValueError):
        controlador(lago, selecao, "falha", "ci", executor_sintetico("fail"))
    assert (estado / "vigente.json").read_bytes() == b"selecao anterior"
    assert manifesto.read_bytes() == b"manifesto anterior"
    assert not (estado / "publicacoes/preparadas/falha/recibo.json").exists()
    [avaliacao] = [json.loads(p.read_bytes()) for p in (estado / "validacoes").glob("*.json")]
    assert avaliacao["resultado"] == "rejeitada"
    assert avaliacao["motivos"][0]["codigo"] == "test.eleitorado.a"


@pytest.mark.parametrize(
    "defeito,status",
    [
        ("cobertura", "fail"),
        ("sem_site", "pass"),
        ("sem_seed", "pass"),
        ("site_falha", "pass"),
        ("exclude_site", "pass"),
        ("invocacao", "fail"),
        ("args", "fail"),
        ("target_path", "fail"),
        ("sem_artefatos", "fail"),
        (None, "error"),
        (None, "warn"),
    ],
)
def test_falha_operacional_ou_incompleta_inconclusiva(candidato, defeito, status):
    lago, selecao = candidato
    with pytest.raises(ValueError):
        controlador(
            lago, selecao, "inconclusiva", "ci", executor_sintetico(status, defeito=defeito)
        )
    avaliacoes = [
        json.loads(p.read_bytes()) for p in (lago / "estado/tse/validacoes").glob("*.json")
    ]
    assert avaliacoes and all(a["resultado"] == "inconclusiva" for a in avaliacoes)
    assert not (lago / "estado/tse/vigente.json").exists()


def test_promocao_exige_evidencia_e_supera_todas_rejeicoes(candidato):
    lago, selecao = candidato
    referencias = []
    for i in range(2):
        referencias.append(
            gravar_avaliacao(
                lago,
                escopo="selecao",
                identidade=selecao.selecao_id,
                entradas_digest=digest_entradas(lago, selecao),
                contrato="tse:selecao:v1",
                execucao_id=f"anterior-{i}",
                resultado="rejeitada",
                motivos=[],
            )
        )
    gravar_avaliacao(
        lago,
        escopo="selecao",
        identidade=selecao.selecao_id,
        entradas_digest=digest_entradas(lago, selecao),
        contrato="tse:selecao:v1",
        execucao_id="isolada",
        resultado="aprovada",
        motivos=[],
        superadas=tuple(referencias),
        evidencia="isolada",
    )
    recibo = controlador(lago, selecao, "nova", "ci", executor_sintetico())
    conferir_recibo_tse(lago, selecao, recibo)
    dados = json.loads((lago / "estado/tse/publicacoes/preparadas/nova/recibo.json").read_bytes())
    assert sorted(dados["superadas"]) == sorted(referencias)
    assert (
        json.loads((lago / "estado/tse/vigente.json").read_bytes())["selecao_id"]
        == selecao.selecao_id
    )
    with pytest.raises(FileExistsError):
        controlador(lago, selecao, "nova", "ci", executor_sintetico())


def test_recibo_outra_selecao_rejeitado(candidato, monkeypatch):
    from coletor.tse import pipeline

    lago, selecao = candidato
    original = pipeline.emitir_recibo
    monkeypatch.setattr(
        pipeline,
        "emitir_recibo",
        lambda *a, **kw: replace(original(*a, **kw), selecao_digest="0" * 64),
    )
    with pytest.raises(ValueError) as erro:
        controlador(lago, selecao, "trocado", "ci", executor_sintetico())
    assert "outra sele" in str(erro.value.__cause__)
    assert not (lago / "estado/tse/vigente.json").exists()


@pytest.mark.parametrize("valor", [1, None])
def test_produtor_artefatos_dbt_reais(candidato, tmp_path, valor):
    lago, selecao = candidato
    projeto = tmp_path / "projeto"
    (projeto / "models").mkdir(parents=True)
    (projeto / "dbt_project.yml").write_text(
        "name: eleitorado\nversion: '1.0'\nconfig-version: 2\n"
        "profile: teste\nflags:\n  send_anonymous_usage_stats: false\n",
        encoding="utf-8",
    )
    (projeto / "profiles.yml").write_text(
        "teste:\n  target: ci\n  outputs:\n    ci:\n      type: duckdb\n"
        "      path: ':memory:'\n      threads: 1\n",
        encoding="utf-8",
    )
    (projeto / "models/resumo.sql").write_text(
        "{{ config(materialized='external', location=var('tse_saida') ~ "
        "'/resumo.parquet') }} select "
        + ("null::integer" if valor is None else "1")
        + " as quantidade",
        encoding="utf-8",
    )
    (projeto / "models/schema.yml").write_text(
        "version: 2\nmodels:\n- name: resumo\n  columns:\n"
        "  - name: quantidade\n    data_tests: [not_null]\n",
        encoding="utf-8",
    )
    if valor is None:
        with pytest.raises(ValueError, match="teste de dados"):
            controlador(lago, selecao, "real", "ci", partial(rodar_dbt, projeto))
        [avaliacao] = [
            json.loads(p.read_bytes()) for p in (lago / "estado/tse/validacoes").glob("*.json")
        ]
        assert avaliacao["resultado"] == "rejeitada"
        assert not (lago / "estado/tse/vigente.json").exists()
        return
    recibo = controlador(lago, selecao, "real", "ci", partial(rodar_dbt, projeto))
    conferir_recibo_tse(lago, selecao, recibo)
    pasta = lago / "estado/tse/publicacoes/preparadas/real"
    selo = json.loads((pasta / "execucao.json").read_bytes())
    assert str(uuid.UUID(selo["invocation_id"])) == selo["invocation_id"]
    assert selo["invocation_id"] != "real"
    assert (
        selo["comando"][selo["comando"].index("--target-path") + 1]
        == (pasta / "dbt-target").as_posix()
    )
    assert (pasta / "manifest.json").read_bytes() == (
        pasta / "dbt-target/manifest.json"
    ).read_bytes()


@pytest.mark.parametrize("anterior", [None, "dados"])
def test_bootstrap_dbt_real_com_lago_relativo(tmp_path, monkeypatch, anterior):
    import os
    from pathlib import Path

    from coletor.dbt import ambiente_dbt
    from coletor.tse.execucao import preparar_execucao_tse

    monkeypatch.chdir(tmp_path)
    if anterior is None:
        monkeypatch.delenv("ELEITORADO_LAGO", raising=False)
    else:
        monkeypatch.setenv("ELEITORADO_LAGO", anterior)
    preparada = preparar_execucao_tse(Path("dados"), "bootstrap", "ci")
    projeto = tmp_path / "projeto"
    (projeto / "models").mkdir(parents=True)
    (projeto / "macros").mkdir()
    (projeto / "macros/tse.sql").write_bytes((RAIZ / "dbt/macros/tse.sql").read_bytes())
    (projeto / "dbt_project.yml").write_text(
        "name: eleitorado\nversion: '1.0'\nconfig-version: 2\n"
        "profile: teste\nflags:\n  send_anonymous_usage_stats: false\n",
        encoding="utf-8",
    )
    (projeto / "profiles.yml").write_text(
        "teste:\n  outputs:\n    ci:\n      type: duckdb\n"
        "      path: ':memory:'\n      threads: 1\n",
        encoding="utf-8",
    )
    (projeto / "models/bootstrap.sql").write_text(
        "select count(*) as quantidade from {{ fonte_tse('bens') }}", encoding="utf-8"
    )
    with ambiente_dbt(Path("dados"), Path("publico")):
        resultado = rodar_dbt(
            projeto, "ci", Path("publico"), ["--vars", json.dumps(preparada.vars_dbt)]
        )
    assert resultado == ResultadoDbt("sucesso", 0)
    assert os.environ.get("ELEITORADO_LAGO") == anterior
    compilado = (projeto / "target/compiled/eleitorado/models/bootstrap.sql").read_text("utf-8")
    assert (tmp_path / "dados/estado/tse/ci/bens/vazio/vazio.parquet").as_posix() in compilado
    assert not preparada.publicavel


def test_interrupcao_registrada_inconclusiva(candidato):
    lago, selecao = candidato

    def interromper(**kwargs):
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        controlador(lago, selecao, "interrompida", "ci", interromper)
    [avaliacao] = [
        json.loads(p.read_bytes()) for p in (lago / "estado/tse/validacoes").glob("*.json")
    ]
    assert avaliacao["resultado"] == "inconclusiva"
    assert not (lago / "estado/tse/vigente.json").exists()


@pytest.mark.parametrize("alteracao", ["entrada", "descritor"])
def test_entrada_alterada_durante_falha_nao_rejeita_digest_antigo(candidato, alteracao):
    from pathlib import Path

    lago, selecao = candidato

    def executar(**kwargs):
        resultado = executor_sintetico("fail")(**kwargs)
        if alteracao == "entrada":
            argumentos = kwargs["argumentos"]
            variaveis = json.loads(argumentos[argumentos.index("--vars") + 1])
            caminho = Path(variaveis["tse_fontes"]["bens"][0])
            caminho.write_bytes(caminho.read_bytes() + b"alterado durante build")
        else:
            versao = selecao.versoes["tse.bens:2018"]
            caminho = lago / f"estado/tse/versoes/{versao}.json"
            dados = json.loads(caminho.read_bytes())
            dados["nota_teste"] = "alterado durante build"
            caminho.write_text(json.dumps(dados), encoding="utf-8")
        return resultado

    with pytest.raises(ValueError):
        controlador(lago, selecao, "alterada", "ci", executar)
    avaliacoes = [
        json.loads(p.read_bytes()) for p in (lago / "estado/tse/validacoes").glob("*.json")
    ]
    assert avaliacoes and all(a["resultado"] == "inconclusiva" for a in avaliacoes)
    assert not (lago / "estado/tse/vigente.json").exists()
