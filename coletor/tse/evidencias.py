"""Protocolo privado de evidências TSE produzido pelo controlador confiável."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from coletor.hashes import json_canonico, sha256_arquivo

PROTOCOLO_PREPARACAO = "tse:preparacao:v1"
PROTOCOLO_EXECUCAO = "tse:execucao:v1"


def inventario_saida(pasta: Path) -> list[dict]:
    if not pasta.is_dir() or pasta.is_symlink():
        raise ValueError("saída preparada ausente ou simbólica")
    inventario = []
    for caminho in sorted(pasta.rglob("*")):
        if caminho.is_symlink() or not caminho.resolve().is_relative_to(pasta.resolve()):
            raise ValueError("saída fora da pasta preparada")
        if caminho.is_file():
            inventario.append(
                {
                    "caminho": caminho.relative_to(pasta).as_posix(),
                    "tamanho": caminho.stat().st_size,
                    "sha256": sha256_arquivo(caminho),
                }
            )
    if not inventario:
        raise ValueError("saída preparada vazia")
    return inventario


def _comando(comando, preparacao) -> bool:
    if not isinstance(comando, list) or comando[:2] != ["dbt", "build"]:
        raise ValueError("evidência deve executar dbt build completo")
    opcoes = {}
    argumentos = comando[2:]
    if len(argumentos) % 2:
        raise ValueError("argumentos dbt inválidos")
    permitidas = {
        "--target",
        "--vars",
        "--project-dir",
        "--profiles-dir",
        "--target-path",
        "--exclude-resource-type",
    }
    for opcao, valor in zip(argumentos[::2], argumentos[1::2], strict=True):
        if opcao == "--exclude-resource-types":
            opcao = "--exclude-resource-type"
        if opcao not in permitidas or opcao in opcoes or not isinstance(valor, str):
            raise ValueError("seleção parcial ou opção dbt não autorizada")
        opcoes[opcao] = valor
    if opcoes.get("--target") != preparacao["target"]:
        raise ValueError("target executado divergente")
    if json.loads(opcoes.get("--vars", "null")) != preparacao["vars"]:
        raise ValueError("vars executadas divergentes")
    exclusao = opcoes.get("--exclude-resource-type")
    if exclusao not in (None, "unit_test"):
        raise ValueError("apenas exclusão de unit_test é autorizada")
    return exclusao == "unit_test"


def conferir_execucao(pasta: Path, esperado: dict, resultado):
    """Confere arquivos contra expectativa recalculada pelo consumidor; sem acesso à seleção."""
    for nome in ("preparacao.json", "execucao.json", "manifest.json", "run_results.json"):
        arquivo = pasta / nome
        if arquivo.is_symlink() or not arquivo.resolve().is_relative_to(pasta.resolve()):
            raise ValueError("artefato fora da execução preparada")
    preparacao = json.loads((pasta / "preparacao.json").read_bytes())
    selo = json.loads((pasta / "execucao.json").read_bytes())
    saida = inventario_saida(pasta / "marts")
    if any(preparacao.get(k) != v for k, v in esperado.items()):
        raise ValueError("preparação incompleta ou vars/caminhos divergentes")
    if any(
        selo.get(k) != esperado[k]
        for k in (
            "execucao_id",
            "selecao_digest",
            "entradas_digest",
            "vars_digest",
        )
    ):
        raise ValueError("execução pertence a outra seleção ou entradas")
    if not isinstance(preparacao.get("target"), str) or not preparacao["target"]:
        raise ValueError("target preparado ausente")
    if selo.get("protocolo") != PROTOCOLO_EXECUCAO:
        raise ValueError("protocolo de execução inválido")
    if selo.get("preparacao_sha256") != sha256_arquivo(pasta / "preparacao.json"):
        raise ValueError("preparação foi alterada após execução")
    if type(selo.get("retorno")) is not int or selo["retorno"] != 0:
        raise ValueError("processo dbt não terminou com sucesso")
    if (
        resultado.status != "sucesso"
        or type(resultado.testes_com_erro) is not int
        or resultado.testes_com_erro != 0
    ):
        raise ValueError("resultado dbt não comprovou sucesso completo")
    if selo.get("resultado") != asdict(resultado):
        raise ValueError("resultado solto diverge do processo selado")
    if (
        selo.get("saida") != saida
        or selo.get("saida_digest") != hashlib.sha256(json_canonico(saida).encode()).hexdigest()
    ):
        raise ValueError("saída candidata foi alterada")
    excluir_unitarios = _comando(selo.get("comando"), preparacao)
    artefatos = {}
    for nome in ("manifest", "run_results"):
        caminho = pasta / f"{nome}.json"
        if selo.get(f"{nome}_sha256") != sha256_arquivo(caminho):
            raise ValueError("artefato dbt foi alterado")
        artefatos[nome] = json.loads(caminho.read_bytes())
        if (
            not selo.get("invocation_id")
            or artefatos[nome].get("metadata", {}).get("invocation_id") != selo["invocation_id"]
        ):
            raise ValueError("artefatos dbt de invocações diferentes")
    args = artefatos["run_results"].get("args", {})
    if (
        args.get("which") != "build"
        or args.get("target") != preparacao["target"]
        or args.get("vars") != preparacao["vars"]
    ):
        raise ValueError("argumentos dos artefatos divergentes")
    if args.get("select") or args.get("exclude") or args.get("resource_types"):
        raise ValueError("artefato de build parcial")
    if args.get("exclude_resource_types", []) != (["unit_test"] if excluir_unitarios else []):
        raise ValueError("exclusões dos artefatos divergem do comando autorizado")
    obrigatorios = {}
    manifesto = artefatos["manifest"]
    for identificador, no in {
        **manifesto.get("nodes", {}),
        **manifesto.get("unit_tests", {}),
    }.items():
        if no.get("config", {}).get("enabled", True) is not True:
            continue
        tipo = no.get("resource_type")
        if tipo == "unit_test" and excluir_unitarios:
            continue  # CI executa unitários; produção exclui só este tipo, como rodar_dbt.
        if tipo == "analysis":
            continue  # dbt build não executa análises.
        if tipo == "model" and no.get("config", {}).get("materialized") == "ephemeral":
            continue  # Compilado no modelo consumidor, sem run_result próprio.
        if tipo not in ("model", "seed", "snapshot", "test", "unit_test"):
            raise ValueError("tipo de nó dbt desconhecido no manifesto")
        obrigatorios[identificador] = "pass" if tipo in ("test", "unit_test") else "success"
    resultados = artefatos["run_results"].get("results")
    if not obrigatorios or not isinstance(resultados, list) or not resultados:
        raise ValueError("cobertura dbt vazia")
    vistos = set()
    for item in resultados:
        identificador = item.get("unique_id")
        if identificador in vistos or identificador not in obrigatorios:
            raise ValueError("nó dbt duplicado ou fora do manifesto")
        vistos.add(identificador)
        if item.get("status") != obrigatorios[identificador]:
            raise ValueError("dbt contém warn/skip/falha ou status desconhecido")
    if vistos != set(obrigatorios):
        raise ValueError("cobertura obrigatória dbt incompleta")
    return selo
