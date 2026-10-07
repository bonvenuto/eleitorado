"""Seleções TSE sintéticas: nenhuma promoção parcial ou recibo reaproveitado."""

import hashlib
import json
from dataclasses import replace
from datetime import date

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from coletor.adaptadores.base import Extracao
from coletor.adaptadores.tse_zip import preparar_familias
from coletor.competencias import Competencia
from coletor.conversao import Controle
from coletor.dbt import ResultadoDbt
from coletor.hashes import json_canonico, sha256_arquivo
from coletor.manifesto import RecursoCompleto
from coletor.tse.evidencias import inventario_saida
from coletor.tse.modelos import ReciboValidacaoTse, VersaoTse
from coletor.tse.selecao import (
    criar_selecao,
    digest_entradas,
    digest_saida,
    digest_selecao,
    emitir_recibo,
    inventario_entradas,
    promover_selecao,
    validar_selecao,
    vars_selecao,
)
from coletor.tse.validacoes import gravar_avaliacao, rejeicoes_pendentes
from coletor.tse.versoes import gravar_versao
from tests.amostras import AGORA
from tests.amostras_tse import recurso_tse, zip_tse
from tests.test_tse_zip import CABECALHOS, csv_sintetico


def versao(lago, pasta, recurso_id, ano, total=100):
    pasta.mkdir(parents=True, exist_ok=True)
    recurso = RecursoCompleto("tse", recurso_tse(recurso_id))
    membros = {}
    for template in recurso.recurso.familias.values():
        nome = template.format(ano=ano)
        header = CABECALHOS[ano, nome]
        linha = ["sintético"] * len(header)
        linha[header.index("DT_GERACAO")] = f"01/10/{ano}"
        linha[header.index("HH_GERACAO")] = "12:00:00"
        if "VR_BEM_CANDIDATO" in header:
            linha[header.index("VR_BEM_CANDIDATO")] = str(total)
        membros[nome] = csv_sintetico(header, [linha])
    original = pasta / "original.zip"
    original.write_bytes(zip_tse(membros))
    comp = Competencia.de_ano(ano)
    extracao = Extracao(
        comp,
        original,
        "zip",
        recurso.recurso.url.format(ano=ano),
        200,
        original.stat().st_size,
        sha256_arquivo(original),
    )
    familias = preparar_familias(recurso.recurso, comp, original, pasta)
    controle = Controle("coleta", str(ano), comp.data, "gs://teste/original.zip", AGORA)
    return gravar_versao(lago, recurso, extracao, familias, controle)


def versao_sintetica(lago, recurso_id, ano):
    # Fixture independente do instalador T4: hashes de bytes reais e esquema explícito.
    recurso = recurso_tse(recurso_id)
    recurso_completo = f"tse.{recurso_id}"
    sha_zip = hashlib.sha256(zip_tse({"amostra.csv": f"{recurso_id}-{ano}".encode()})).hexdigest()
    identificador = hashlib.sha256(
        json_canonico([recurso_completo, ano, sha_zip]).encode()
    ).hexdigest()
    familias, hashes, layouts, hashes_parquet, membros = {}, {}, {}, {}, {}
    for familia, template in recurso.familias.items():
        membro = template.format(ano=ano)
        header = CABECALHOS[ano, membro]
        linha = ["sintético"] * len(header)
        linha[header.index("DT_GERACAO")] = f"01/10/{ano}"
        linha[header.index("HH_GERACAO")] = "12:00:00"
        if "VR_BEM_CANDIDATO" in header:
            linha[header.index("VR_BEM_CANDIDATO")] = "100"
        caminho = f"raw/tse/{familia}/{ano}/{sha_zip}/dados.parquet"
        raw = lago / caminho
        raw.parent.mkdir(parents=True, exist_ok=True)
        campos = [pa.field(c.lower(), pa.string()) for c in header] + [
            pa.field("_coleta_id", pa.string()),
            pa.field("_competencia", pa.string()),
            pa.field("_competencia_data", pa.date32()),
            pa.field("_linha", pa.int64()),
            pa.field("_arquivo_original", pa.string()),
            pa.field("_carregado_em", pa.timestamp("us", tz="UTC")),
        ]
        valores = linha + ["coleta", str(ano), date(ano, 1, 1), 1, "gs://teste/original.zip", AGORA]
        tabela = pa.Table.from_arrays(
            [pa.array([v], type=c.type) for c, v in zip(campos, valores, strict=True)],
            schema=pa.schema(campos),
        )
        pq.write_table(tabela, raw)
        familias[familia] = caminho
        hashes[familia] = hashlib.sha256(csv_sintetico(header, [linha])).hexdigest()
        layouts[familia] = f"tse:{familia}:{ano}:v1"
        hashes_parquet[familia] = sha256_arquivo(raw)
        membros[familia] = membro
    dados = {
        "recurso_id": recurso_completo,
        "ano": ano,
        "versao_id": identificador,
        "sha256_zip": sha_zip,
        "familias": familias,
        "hashes": hashes,
        "layouts": layouts,
        "sha256_semantico": hashlib.sha256(b"semantica sintetica").hexdigest(),
        "hashes_parquet": hashes_parquet,
        "membros": membros,
        "contagens": {f: 1 for f in familias},
        "geracoes": {f: [[f"01/10/{ano}", "12:00:00"]] for f in familias},
        "url": recurso.url.format(ano=ano),
        "arquivo_original": "gs://teste/original.zip",
        "coleta_id": "coleta",
    }
    pasta = lago / "estado/tse/versoes"
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / f"{identificador}.json").write_text(json_canonico(dados), encoding="utf-8")
    return VersaoTse(
        recurso_completo,
        ano,
        identificador,
        sha_zip,
        familias,
        hashes,
        layouts,
        dados["sha256_semantico"],
    )


def montar_vetor(tmp_path, integrar=False):
    lago = tmp_path / "lago"
    versoes = {}
    for recurso in ("candidaturas", "bens", "contas"):
        for ano in (2018, 2020, 2022, 2024):
            if integrar and recurso == "bens" and ano == 2024:
                v = versao(lago, tmp_path / "original-integrado", recurso, ano)
            else:
                v = versao_sintetica(lago, recurso, ano)
            versoes[f"tse.{recurso}:{ano}"] = v.versao_id
    return lago, criar_selecao(versoes)


@pytest.fixture
def vetor(tmp_path):
    return montar_vetor(tmp_path)


def execucao(
    lago,
    selecao,
    nome="execucao-1",
    resultado=None,
    superadas=(),
    vars_extras=None,
    excluir_unitarios=False,
):
    pasta = lago / "estado/tse/publicacoes/preparadas" / nome
    (pasta / "marts").mkdir(parents=True, exist_ok=True)
    (pasta / "marts/resumo.parquet").write_bytes(b"saida sintetica")

    def digest(dados):
        return hashlib.sha256(json_canonico(dados).encode()).hexdigest()

    variaveis = {**vars_selecao(lago, selecao, nome), **(vars_extras or {})}
    preparacao = {
        "protocolo": "tse:preparacao:v1",
        "execucao_id": nome,
        "target": "ci",
        "selecao": {"selecao_id": selecao.selecao_id, "versoes": selecao.versoes},
        "selecao_digest": digest_selecao(selecao),
        "entradas": inventario_entradas(lago, selecao),
        "entradas_digest": digest_entradas(lago, selecao),
        "vars": variaveis,
        "vars_digest": digest(variaveis),
        "saida": f"estado/tse/publicacoes/preparadas/{nome}/marts",
        "contrato": "tse:selecao:v1",
    }
    (pasta / "preparacao.json").write_text(json_canonico(preparacao), encoding="utf-8")
    resultados = [
        {"unique_id": "test.tse.cobertura", "status": "pass"},
        {"unique_id": "model.tse.resumo", "status": "success"},
    ]
    if not excluir_unitarios:
        resultados.append({"unique_id": "unit_test.tse.exemplo", "status": "pass"})
    (pasta / "run_results.json").write_text(
        json_canonico(
            {
                "metadata": {"invocation_id": "uuid-dbt-distinto"},
                "args": {
                    "which": "build",
                    "target": "ci",
                    "vars": variaveis,
                    "exclude_resource_types": ["unit_test"] if excluir_unitarios else [],
                },
                "results": resultados,
            }
        ),
        encoding="utf-8",
    )
    (pasta / "manifest.json").write_text(
        json_canonico(
            {
                "metadata": {"invocation_id": "uuid-dbt-distinto"},
                "nodes": {
                    "test.tse.cobertura": {"resource_type": "test", "config": {"enabled": True}},
                    "model.tse.resumo": {"resource_type": "model", "config": {"enabled": True}},
                },
                "unit_tests": {
                    "unit_test.tse.exemplo": {
                        "resource_type": "unit_test",
                        "config": {"enabled": True},
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    selo = {
        "protocolo": "tse:execucao:v1",
        "execucao_id": nome,
        "preparacao_sha256": sha256_arquivo(pasta / "preparacao.json"),
        "invocation_id": "uuid-dbt-distinto",
        "manifest_sha256": sha256_arquivo(pasta / "manifest.json"),
        "run_results_sha256": sha256_arquivo(pasta / "run_results.json"),
        "selecao_digest": digest_selecao(selecao),
        "entradas_digest": digest_entradas(lago, selecao),
        "vars_digest": digest(variaveis),
        "saida": inventario_saida(pasta / "marts"),
        "saida_digest": digest_saida(lago, nome),
        "comando": ["dbt", "build", "--target", "ci", "--vars", json_canonico(variaveis)]
        + (["--exclude-resource-type", "unit_test"] if excluir_unitarios else []),
        "retorno": 0,
        "resultado": {"status": "sucesso", "testes_com_erro": 0},
    }
    (pasta / "execucao.json").write_text(json_canonico(selo), encoding="utf-8")
    return emitir_recibo(
        lago,
        selecao,
        nome,
        resultado or ResultadoDbt("sucesso", 0),
        superadas=superadas,
    )


def vigente(lago):
    return (lago / "estado/tse/vigente.json").read_bytes()


def test_retificacao_menor(tmp_path):
    lago, primeira = montar_vetor(tmp_path, integrar=True)
    promover_selecao(lago, primeira, execucao(lago, primeira))
    nova = versao(lago, tmp_path / "retificada", "bens", 2024, total=80)
    segunda = criar_selecao({**primeira.versoes, "tse.bens:2024": nova.versao_id})
    promover_selecao(lago, segunda, execucao(lago, segunda, "execucao-2"))
    escolhida = json.loads(vigente(lago))
    assert escolhida["versoes"]["tse.bens:2024"] == nova.versao_id
    assert pq.read_table(lago / nova.familias["bens"])["vr_bem_candidato"].to_pylist() == ["80"]
    assert len(list(lago.glob("raw/tse/bens/2024/*/dados.parquet"))) == 2
    assert len(list(lago.glob("estado/tse/selecoes/*.json"))) == 2
    (lago / "estado/tse/vigente.json").unlink()
    assert (lago / "estado/tse/inicializado.json").is_file()


@pytest.mark.parametrize("defeito", ["hash", "faltante", "layout", "schema", "crc"])
def test_falha_conserva_vigente(vetor, defeito):
    lago, selecao = vetor
    recibo = execucao(lago, selecao)
    promover_selecao(lago, selecao, recibo)
    anterior = vigente(lago)
    descritor = lago / "estado/tse/versoes" / f"{selecao.versoes['tse.bens:2024']}.json"
    dados = json.loads(descritor.read_bytes())
    raw = lago / dados["familias"]["bens"]
    if defeito in ("hash", "crc"):
        raw.write_bytes(b"corrompido")
        if defeito == "crc":
            dados["hashes_parquet"]["bens"] = sha256_arquivo(raw)
    elif defeito == "faltante":
        raw.unlink()
    elif defeito == "layout":
        dados["layouts"]["bens"] = "desconhecido"
    else:
        tabela = pq.read_table(raw).drop(["vr_bem_candidato"])
        pq.write_table(tabela, raw)
        dados["hashes_parquet"]["bens"] = sha256_arquivo(raw)
    descritor.write_text(json_canonico(dados), encoding="utf-8")
    assert validar_selecao(lago, selecao)
    with pytest.raises(ValueError):
        promover_selecao(lago, selecao, recibo)
    assert vigente(lago) == anterior


def test_cobertura_exige_doze_e_identidade(vetor):
    lago, selecao = vetor
    assert validar_selecao(lago, selecao) == ()
    parcial = criar_selecao({k: v for k, v in selecao.versoes.items() if k != "tse.bens:2018"})
    assert validar_selecao(lago, parcial)
    assert validar_selecao(lago, replace(selecao, selecao_id="0" * 64))


@pytest.mark.parametrize("defeito", ["selecao", "entradas", "saida", "execucao", "dbt"])
def test_recibo_nao_reaproveita_sucesso(vetor, defeito):
    lago, selecao = vetor
    recibo = execucao(lago, selecao)
    if defeito == "saida":
        (lago / "estado/tse/publicacoes/preparadas/execucao-1/marts/resumo.parquet").write_bytes(
            b"outra"
        )
    elif defeito == "dbt":
        recibo = replace(recibo, resultado=ResultadoDbt("falha", 1))
    else:
        campo = {
            "selecao": "selecao_digest",
            "entradas": "entradas_digest",
            "execucao": "execucao_id",
        }[defeito]
        recibo = replace(recibo, **{campo: "0" * 64})
    with pytest.raises(ValueError):
        promover_selecao(lago, selecao, recibo)
    assert not (lago / "estado/tse/vigente.json").exists()


def test_resultado_solto_nao_e_evidencia(vetor):
    lago, selecao = vetor
    recibo = ReciboValidacaoTse(
        digest_selecao(selecao),
        "inexistente",
        digest_entradas(lago, selecao),
        "0" * 64,
        ResultadoDbt("sucesso", 0),
    )
    with pytest.raises(ValueError):
        promover_selecao(lago, selecao, recibo)


def test_hash_rejeitado_nao_promove(vetor):
    lago, selecao = vetor
    recibo = execucao(lago, selecao)
    rejeicao = gravar_avaliacao(
        lago,
        escopo="selecao",
        identidade=selecao.selecao_id,
        entradas_digest=recibo.entradas_digest,
        contrato="tse:selecao:v1",
        execucao_id="anterior",
        resultado="rejeitada",
        motivos=[{"codigo": "dbt", "mensagem": "falha semântica"}],
    )
    with pytest.raises(ValueError):
        promover_selecao(lago, selecao, recibo)
    assert not (lago / "estado/tse/vigente.json").exists()
    novo = execucao(lago, selecao, "execucao-2", superadas=(rejeicao,))
    promover_selecao(lago, selecao, novo)
    assert (
        rejeicoes_pendentes(
            lago,
            escopo="selecao",
            identidade=selecao.selecao_id,
            entradas_digest=novo.entradas_digest,
            contrato="tse:selecao:v1",
        )
        == []
    )


def test_caminho_fora_raw_e_tipo_incorreto_bloqueados(vetor):
    lago, selecao = vetor
    caminho = lago / "estado/tse/versoes" / f"{selecao.versoes['tse.bens:2024']}.json"
    dados = json.loads(caminho.read_bytes())
    dados["familias"]["bens"] = "../fora.parquet"
    caminho.write_text(json_canonico(dados), encoding="utf-8")
    assert validar_selecao(lago, selecao)
    dados["contagens"]["bens"] = True
    caminho.write_text(json_canonico(dados), encoding="utf-8")
    assert validar_selecao(lago, selecao)


def test_saida_digest_muda_com_arquivo_adicionado(vetor):
    lago, selecao = vetor
    recibo = execucao(lago, selecao)
    (lago / "estado/tse/publicacoes/preparadas/execucao-1/marts/extra.parquet").write_bytes(
        b"extra"
    )
    assert digest_saida(lago, "execucao-1") != recibo.saida_digest


@pytest.mark.parametrize(
    "defeito",
    [
        "invocacao",
        "warn",
        "skip",
        "duplicado",
        "vazio",
        "cobertura",
        "parcial",
        "vars",
        "target",
        "retorno",
        "selo",
        "preparacao",
        "hash_artefato",
        "tipo_no",
        "exclusao_divergente",
        "exclusao_dados",
        "unitario_ausente",
    ],
)
def test_evidencia_incompleta_nao_emite_recibo(vetor, defeito):
    lago, selecao = vetor
    execucao(lago, selecao)
    pasta = lago / "estado/tse/publicacoes/preparadas/execucao-1"
    (pasta / "recibo.json").unlink()
    resultados = json.loads((pasta / "run_results.json").read_bytes())
    selo = json.loads((pasta / "execucao.json").read_bytes())
    manifesto = json.loads((pasta / "manifest.json").read_bytes())
    if defeito == "invocacao":
        resultados["metadata"]["invocation_id"] = "outra"
    elif defeito in ("warn", "skip"):
        resultados["results"][0]["status"] = defeito
    elif defeito == "duplicado":
        resultados["results"].append(resultados["results"][0])
    elif defeito == "vazio":
        resultados["results"] = []
    elif defeito == "cobertura":
        resultados["results"].pop()
    elif defeito == "parcial":
        selo["comando"].extend(["--select", "model.tse.resumo"])
    elif defeito == "vars":
        resultados["args"]["vars"] = {}
    elif defeito == "target":
        resultados["args"]["target"] = "prod"
    elif defeito == "exclusao_divergente":
        resultados["args"]["exclude_resource_types"] = ["unit_test"]
    elif defeito == "exclusao_dados":
        selo["comando"].extend(["--exclude-resource-type", "test"])
        resultados["args"]["exclude_resource_types"] = ["test"]
    elif defeito == "unitario_ausente":
        resultados["results"] = [
            r for r in resultados["results"] if not r["unique_id"].startswith("unit_test.")
        ]
    elif defeito == "retorno":
        selo["retorno"] = 1
    elif defeito == "selo":
        selo["selecao_digest"] = "0" * 64
    elif defeito == "preparacao":
        (pasta / "preparacao.json").write_text("{}", encoding="utf-8")
    elif defeito == "tipo_no":
        manifesto["nodes"]["model.tse.resumo"]["resource_type"] = "desconhecido"
    (pasta / "manifest.json").write_text(json_canonico(manifesto), encoding="utf-8")
    (pasta / "run_results.json").write_text(json_canonico(resultados), encoding="utf-8")
    selo["manifest_sha256"] = sha256_arquivo(pasta / "manifest.json")
    if defeito != "hash_artefato":
        selo["run_results_sha256"] = sha256_arquivo(pasta / "run_results.json")
    else:
        selo["run_results_sha256"] = "0" * 64
    (pasta / "execucao.json").write_text(json_canonico(selo), encoding="utf-8")
    with pytest.raises(ValueError):
        emitir_recibo(lago, selecao, "execucao-1", ResultadoDbt("sucesso", 0))
    assert not (pasta / "recibo.json").exists()


def test_superacao_inexistente_nao_deixa_recibo(vetor):
    lago, selecao = vetor
    execucao(lago, selecao)
    pasta = lago / "estado/tse/publicacoes/preparadas/execucao-1"
    (pasta / "recibo.json").unlink()
    with pytest.raises(ValueError):
        emitir_recibo(
            lago, selecao, "execucao-1", ResultadoDbt("sucesso", 0), superadas=("0" * 64,)
        )
    assert not (pasta / "recibo.json").exists()


def test_tipos_invalidos_retornam_impedimentos(vetor):
    lago, selecao = vetor
    invalida = replace(selecao, versoes={1: "0" * 64, "texto": "0" * 64})
    assert validar_selecao(lago, invalida)


def test_aprovacao_solteira_nao_reabilita_recibo_antigo(vetor):
    lago, selecao = vetor
    recibo = execucao(lago, selecao)
    pasta = lago / "estado/tse/publicacoes/preparadas/execucao-1"
    evidencia_antiga = json.loads((pasta / "recibo.json").read_bytes())["evidencia"]
    rejeicao = gravar_avaliacao(
        lago,
        escopo="selecao",
        identidade=selecao.selecao_id,
        entradas_digest=recibo.entradas_digest,
        contrato="tse:selecao:v1",
        execucao_id="rejeitada",
        resultado="rejeitada",
        motivos=[],
    )
    gravar_avaliacao(
        lago,
        escopo="selecao",
        identidade=selecao.selecao_id,
        entradas_digest=recibo.entradas_digest,
        contrato="tse:selecao:v1",
        execucao_id="aprovacao-sem-build",
        resultado="aprovada",
        motivos=[],
        superadas=(rejeicao,),
        evidencia=evidencia_antiga,
    )
    with pytest.raises(ValueError):
        promover_selecao(lago, selecao, recibo)
    assert not (lago / "estado/tse/vigente.json").exists()


def test_vars_extras_integras_e_troca_detectada(vetor):
    lago, selecao = vetor
    recibo = execucao(lago, selecao, vars_extras={"opcao_exemplo": "original"})
    promover_selecao(lago, selecao, recibo)
    anterior = vigente(lago)
    pasta = lago / "estado/tse/publicacoes/preparadas/execucao-1"
    preparacao = json.loads((pasta / "preparacao.json").read_bytes())
    preparacao["vars"]["opcao_exemplo"] = "trocada"
    (pasta / "preparacao.json").write_text(json_canonico(preparacao), encoding="utf-8")
    with pytest.raises(ValueError):
        promover_selecao(lago, selecao, recibo)
    assert vigente(lago) == anterior


def test_comando_produtivo_exclui_apenas_unitarios(vetor):
    lago, selecao = vetor
    recibo = execucao(lago, selecao, excluir_unitarios=True)
    promover_selecao(lago, selecao, recibo)
    assert json.loads(vigente(lago))["selecao_id"] == selecao.selecao_id


def test_novo_recibo_exige_referencias_mesmo_apos_aprovacao_isolada(vetor):
    lago, selecao = vetor
    antigo = execucao(lago, selecao)
    rejeicao = gravar_avaliacao(
        lago,
        escopo="selecao",
        identidade=selecao.selecao_id,
        entradas_digest=antigo.entradas_digest,
        contrato="tse:selecao:v1",
        execucao_id="rejeitada",
        resultado="rejeitada",
        motivos=[],
    )
    gravar_avaliacao(
        lago,
        escopo="selecao",
        identidade=selecao.selecao_id,
        entradas_digest=antigo.entradas_digest,
        contrato="tse:selecao:v1",
        execucao_id="aprovacao-isolada",
        resultado="aprovada",
        motivos=[],
        superadas=(rejeicao,),
        evidencia="string não comprova execução",
    )
    with pytest.raises(ValueError):
        execucao(lago, selecao, "nova-sem-referencias")
    assert not (
        lago / "estado/tse/publicacoes/preparadas/nova-sem-referencias/recibo.json"
    ).exists()
    novo = execucao(lago, selecao, "nova-com-referencias", superadas=(rejeicao,))
    promover_selecao(lago, selecao, novo)
    assert json.loads(vigente(lago))["selecao_id"] == selecao.selecao_id


def test_promocao_compensa_fsync_pos_troca(tmp_path, monkeypatch):
    from tests.test_tse_estado import falhar_sync_apos_vigente, retificacao_sintetica

    lago, primeira = montar_vetor(tmp_path)
    promover_selecao(lago, primeira, execucao(lago, primeira))
    segunda = retificacao_sintetica(lago, primeira)
    recibo = execucao(lago, segunda, "segunda")
    anterior = vigente(lago)
    falhar_sync_apos_vigente(monkeypatch, lago)
    with pytest.raises(OSError, match="fsync apos"):
        promover_selecao(lago, segunda, recibo)
    assert vigente(lago) == anterior


def test_primeira_promocao_falha_preserva_marcador_e_bloqueia(tmp_path, monkeypatch):
    import os
    from pathlib import Path

    from coletor.tse.durabilidade import (
        ErroCompensacaoTse,
        ErroRecuperacaoTse,
        conferir_recuperacao,
    )

    lago, selecao = montar_vetor(tmp_path)
    recibo = execucao(lago, selecao)
    original = os.replace

    def substituir(de, para):
        if Path(para) == lago / "estado/tse/vigente.json":
            raise OSError("falha primeira troca")
        original(de, para)

    monkeypatch.setattr(os, "replace", substituir)
    with pytest.raises(ErroCompensacaoTse):
        promover_selecao(lago, selecao, recibo)
    assert json.loads((lago / "estado/tse/inicializado.json").read_bytes()) == {
        "protocolo": "tse:inicializado:v1",
        "primeira_selecao_id": selecao.selecao_id,
    }
    assert not (lago / "estado/tse/vigente.json").exists()
    assert validar_selecao(lago, selecao)
    with pytest.raises(ErroRecuperacaoTse):
        conferir_recuperacao(lago)


def test_proveniencia_trocada_rejeitada_mesmo_com_hashes_recalculados(vetor):
    lago, selecao = vetor
    variaveis = vars_selecao(lago, selecao, "trocada")
    mapa = variaveis["tse_proveniencia"]
    caminhos = variaveis["tse_fontes"]["bens"]
    mapa[caminhos[0]], mapa[caminhos[1]] = mapa[caminhos[1]], mapa[caminhos[0]]
    # execucao recalcula vars_digest e todos os artefatos/evidências usando o mapa adulterado.
    with pytest.raises(ValueError, match="vars obrigatórias divergentes"):
        execucao(lago, selecao, "trocada", vars_extras={"tse_proveniencia": mapa})


def test_conferir_recibo_puro_nao_promove_vetor(vetor):
    from coletor.tse.selecao import conferir_recibo_tse

    lago, selecao = vetor
    recibo = execucao(lago, selecao)
    antes = {p.relative_to(lago): p.read_bytes() for p in lago.rglob("*") if p.is_file()}
    assert conferir_recibo_tse(lago, selecao, recibo) is None
    assert {p.relative_to(lago): p.read_bytes() for p in lago.rglob("*") if p.is_file()} == antes
    assert not (lago / "estado/tse/vigente.json").exists()


@pytest.mark.parametrize("consumidor", ["conferir", "promover"])
def test_gate_compartilhado_exige_aprovacao_concreta(vetor, consumidor):
    from coletor.tse.selecao import conferir_recibo_tse

    lago, selecao = vetor
    recibo = execucao(lago, selecao)
    for arquivo in (lago / "estado/tse/validacoes").glob("*.json"):
        arquivo.unlink()
    gravar_avaliacao(
        lago,
        escopo="selecao",
        identidade=selecao.selecao_id,
        entradas_digest=recibo.entradas_digest,
        contrato="tse:selecao:v1",
        execucao_id="solta",
        resultado="aprovada",
        motivos=[],
        evidencia="string isolada",
    )
    conferir = conferir_recibo_tse if consumidor == "conferir" else promover_selecao
    with pytest.raises(ValueError, match="aprova"):
        conferir(lago, selecao, recibo)


@pytest.mark.parametrize("consumidor", ["conferir", "promover"])
@pytest.mark.parametrize("defeito", ["recibo_trocado", "rejeicao_posterior"])
def test_gate_compartilhado_paridade_causal(vetor, consumidor, defeito):
    from coletor.tse.selecao import conferir_recibo_tse

    lago, selecao = vetor
    recibo = execucao(lago, selecao)
    if defeito == "recibo_trocado":
        recibo = replace(recibo, saida_digest="0" * 64)
    else:
        gravar_avaliacao(
            lago,
            escopo="selecao",
            identidade=selecao.selecao_id,
            entradas_digest=recibo.entradas_digest,
            contrato="tse:selecao:v1",
            execucao_id="posterior",
            resultado="rejeitada",
            motivos=[],
        )
    conferir = conferir_recibo_tse if consumidor == "conferir" else promover_selecao
    with pytest.raises(ValueError):
        conferir(lago, selecao, recibo)
