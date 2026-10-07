"""Build privado fresco e promocao somente com evidencia completa da mesma invocacao."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from coletor.dbt import ResultadoDbt, ambiente_dbt
from coletor.hashes import json_canonico, sha256_arquivo
from coletor.tse.durabilidade import gravar_json
from coletor.tse.evidencias import PROTOCOLO_EXECUCAO, inventario_saida
from coletor.tse.execucao import preparar_execucao_tse
from coletor.tse.modelos import ReciboValidacaoTse, SelecaoTse
from coletor.tse.selecao import (
    CONTRATO,
    digest_entradas,
    emitir_recibo,
    promover_selecao,
    rejeicoes_conhecidas,
)
from coletor.tse.validacoes import gravar_avaliacao


def _digest(dados) -> str:
    return hashlib.sha256(json_canonico(dados).encode()).hexdigest()


def _conferir_artefatos(pasta: Path, preparacao: dict, comando: list[str]) -> list[str]:
    """Cobertura completa tambem para distinguir teste falho de erro operacional.

    Retorna exclusivamente data tests fail identificados. Erros, skips, warns e artefatos
    incompletos sao inconclusivos; o consumidor T5 ainda aplica seu gate integral ao sucesso.
    """
    if comando[:2] != ["dbt", "build"] or len(comando[2:]) % 2:
        raise ValueError("comando dbt invalido")
    opcoes = dict(zip(comando[2::2], comando[3::2], strict=True))
    if len(opcoes) * 2 != len(comando[2:]) or set(opcoes) != {
        "--exclude-resource-type",
        "--vars",
        "--target-path",
        "--project-dir",
        "--profiles-dir",
        "--target",
    }:
        raise ValueError("build parcial ou opcoes inesperadas")
    if (
        opcoes["--target"] != preparacao["target"]
        or json.loads(opcoes["--vars"]) != preparacao["vars"]
        or opcoes["--exclude-resource-type"] != "unit_test"
        or Path(opcoes["--target-path"]).resolve() != (pasta / "dbt-target").resolve()
    ):
        raise ValueError("comando diverge da preparacao")
    manifest = json.loads((pasta / "manifest.json").read_bytes())
    run = json.loads((pasta / "run_results.json").read_bytes())
    invocacao = manifest["metadata"]["invocation_id"]
    if (
        str(uuid.UUID(invocacao)) != invocacao
        or invocacao == preparacao["execucao_id"]
        or run["metadata"]["invocation_id"] != invocacao
    ):
        raise ValueError("invocacao dbt ausente ou divergente")
    args = run["args"]
    if (
        args.get("which") != "build"
        or args.get("target") != preparacao["target"]
        or args.get("vars") != preparacao["vars"]
        or args.get("select")
        or args.get("exclude")
        or args.get("resource_types")
        or args.get("exclude_resource_types") != ["unit_test"]
    ):
        raise ValueError("argumentos dbt divergentes ou parciais")
    if any(
        not isinstance(args.get(campo), str)
        or Path(args[campo]).resolve() != Path(opcoes["--" + campo.replace("_", "-")]).resolve()
        for campo in ("project_dir", "profiles_dir", "target_path")
    ):
        raise ValueError("caminhos dos argumentos dbt divergem do comando")
    obrigatorios = {}
    for identificador, no in {
        **manifest.get("nodes", {}),
        **manifest.get("unit_tests", {}),
    }.items():
        if no.get("config", {}).get("enabled", True) is not True:
            continue
        tipo = no.get("resource_type")
        if tipo in ("unit_test", "analysis") or (
            tipo == "model" and no.get("config", {}).get("materialized") == "ephemeral"
        ):
            continue
        if tipo not in ("model", "seed", "snapshot", "test"):
            raise ValueError("tipo desconhecido no manifesto dbt")
        obrigatorios[identificador] = tipo
    vistos, falhas = set(), []
    for no in run["results"]:
        identificador = no["unique_id"]
        if identificador in vistos or identificador not in obrigatorios:
            raise ValueError("resultado dbt duplicado ou fora do manifesto")
        vistos.add(identificador)
        tipo = obrigatorios[identificador]
        status = no["status"]
        if tipo == "test" and status == "fail":
            falhas.append(identificador)
        elif status != ("pass" if tipo == "test" else "success"):
            raise ValueError("erro operacional, warn ou skip no dbt")
    if not obrigatorios or vistos != set(obrigatorios):
        raise ValueError("cobertura dbt incompleta")
    return sorted(falhas)


def preparar_e_promover_tse(
    lago: Path,
    selecao: SelecaoTse,
    execucao_id: str,
    target: str,
    rodar: Callable[..., ResultadoDbt],
) -> ReciboValidacaoTse:
    """Rodar e previamente configurado com diretorio do projeto (por exemplo, partial).

    O callback captura artefatos antes de docs; nunca interpreta ResultadoDbt isolado como
    autorizacao. Cada tentativa usa pasta exclusiva e novo execucao_id, inclusive falhas.
    """
    execucao = preparar_execucao_tse(lago, execucao_id, target, selecao)
    pasta = execucao.saida.parent
    preparacao = json.loads((pasta / "preparacao.json").read_bytes())
    argumentos = [
        "--vars",
        json_canonico(execucao.vars_dbt),
        "--target-path",
        (pasta / "dbt-target").as_posix(),
    ]
    captura = None

    def capturar(comando: list[str], retorno: int, alvo: Path) -> None:
        nonlocal captura
        if captura is not None or alvo.resolve() != (pasta / "dbt-target").resolve():
            raise ValueError("captura repetida ou de outra execucao")
        captura = (list(comando), retorno)
        for nome in ("manifest.json", "run_results.json"):
            origem = alvo / nome
            if origem.is_symlink():
                raise ValueError("artefato simbolico nao autorizado")
            with (pasta / nome).open("xb") as destino:
                destino.write(origem.read_bytes())

    try:
        with ambiente_dbt(lago, pasta / "legado"):
            resultado = rodar(
                target=target, publico=pasta / "legado", argumentos=argumentos, capturar=capturar
            )
        if captura is None or not isinstance(resultado, ResultadoDbt):
            raise ValueError("build sem captura concreta")
        comando, retorno = captura
        if type(retorno) is not int:
            raise ValueError("retorno do processo dbt invalido")
        falhas = _conferir_artefatos(pasta, preparacao, comando)
        if falhas and retorno != 0 and resultado.status == "falha":
            if digest_entradas(lago, selecao) != preparacao["entradas_digest"]:
                raise ValueError("entradas alteradas durante build; falha inconclusiva")
            gravar_avaliacao(
                lago,
                escopo="selecao",
                identidade=selecao.selecao_id,
                entradas_digest=preparacao["entradas_digest"],
                contrato=CONTRATO,
                execucao_id=execucao_id,
                resultado="rejeitada",
                motivos=[{"codigo": f, "detalhe": "teste de dados falhou"} for f in falhas],
            )
            raise FalhaSemanticaTse("teste de dados rejeitou selecao candidata")
        if falhas or retorno != 0 or resultado != ResultadoDbt("sucesso", 0):
            raise ValueError("build nao comprovou sucesso completo")
        saida = inventario_saida(execucao.saida)
        selo = {
            "protocolo": PROTOCOLO_EXECUCAO,
            "execucao_id": execucao_id,
            "preparacao_sha256": sha256_arquivo(pasta / "preparacao.json"),
            "invocation_id": json.loads((pasta / "manifest.json").read_bytes())["metadata"][
                "invocation_id"
            ],
            "manifest_sha256": sha256_arquivo(pasta / "manifest.json"),
            "run_results_sha256": sha256_arquivo(pasta / "run_results.json"),
            "selecao_digest": preparacao["selecao_digest"],
            "entradas_digest": preparacao["entradas_digest"],
            "vars_digest": preparacao["vars_digest"],
            "saida": saida,
            "saida_digest": _digest(saida),
            "comando": comando,
            "retorno": retorno,
            "resultado": asdict(resultado),
        }
        gravar_json(pasta / "execucao.json", selo)
        recibo = emitir_recibo(
            lago,
            selecao,
            execucao_id,
            resultado,
            superadas=tuple(rejeicoes_conhecidas(lago, selecao, digest_entradas(lago, selecao))),
        )
        promover_selecao(lago, selecao, recibo)
        return recibo
    except FalhaSemanticaTse:
        raise
    except (Exception, KeyboardInterrupt) as erro:
        try:
            gravar_avaliacao(
                lago,
                escopo="selecao",
                identidade=selecao.selecao_id,
                entradas_digest=preparacao["entradas_digest"],
                contrato=CONTRATO,
                execucao_id=execucao_id,
                resultado="inconclusiva",
                motivos=[{"codigo": "execucao_inconclusiva", "detalhe": type(erro).__name__}],
            )
        except Exception as falha_persistencia:
            if isinstance(erro, KeyboardInterrupt):
                raise erro from falha_persistencia
            raise
        if isinstance(erro, KeyboardInterrupt):
            raise
        raise ValueError("execucao TSE inconclusiva; selecao anterior preservada") from erro


class FalhaSemanticaTse(ValueError):
    """Falha de dados completa e identificada, registrada antes da interrupcao."""
