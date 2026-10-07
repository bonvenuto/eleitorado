"""Evidências privadas de validação, separadas dos descritores físicos imutáveis."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from coletor.hashes import json_canonico


def gravar_avaliacao(
    lago: Path,
    *,
    escopo: str,
    identidade: str,
    entradas_digest: str,
    contrato: str,
    execucao_id: str,
    resultado: str,
    motivos: list[dict[str, str]],
    superadas: tuple[str, ...] = (),
    evidencia: str | None = None,
) -> str:
    """Publica um JSON completo atomicamente; nova decisão nunca reescreve a antiga."""
    if escopo not in ("versao", "selecao") or resultado not in (
        "rejeitada",
        "aprovada",
        "inconclusiva",
    ):
        raise ValueError("escopo ou resultado de avaliação inválido")
    if superadas and (resultado != "aprovada" or not evidencia):
        raise ValueError("superação exige aprovação completa com evidência explícita")
    if not all(
        re.fullmatch(r"[0-9a-f]{64}", valor) for valor in (identidade, entradas_digest, *superadas)
    ):
        raise ValueError("identidades e referências devem ser SHA-256 hexadecimais")
    pasta = lago / "estado/tse/validacoes"
    for referencia in superadas:
        caminho = pasta / f"{referencia}.json"
        if not caminho.is_file():
            raise ValueError("decisão superada inexistente; avaliação deve ser posterior")
        conteudo_referencia = caminho.read_bytes()
        if hashlib.sha256(conteudo_referencia).hexdigest() != referencia:
            raise ValueError("integridade da decisão superada divergente")
        anterior = json.loads(conteudo_referencia)
        chave = {
            "escopo": escopo,
            "identidade": identidade,
            "entradas_digest": entradas_digest,
            "contrato": contrato,
            "resultado": "rejeitada",
        }
        if any(anterior.get(c) != valor for c, valor in chave.items()):
            raise ValueError("referência não é rejeição da mesma identidade/entradas/contrato")
    dados = {
        "escopo": escopo,
        "identidade": identidade,
        "entradas_digest": entradas_digest,
        "contrato": contrato,
        "execucao_id": execucao_id,
        "resultado": resultado,
        "motivos": motivos,
        "superadas": list(superadas),
        "evidencia": evidencia,
    }
    conteudo = json_canonico(dados).encode("utf-8")
    avaliacao_id = hashlib.sha256(conteudo).hexdigest()
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"{avaliacao_id}.json"
    with tempfile.NamedTemporaryFile(dir=pasta, delete=False) as arquivo:
        temporario = Path(arquivo.name)
        arquivo.write(conteudo)
        arquivo.flush()
        os.fsync(arquivo.fileno())
    try:
        try:
            os.link(temporario, destino)
        except FileExistsError:
            if destino.read_bytes() != conteudo:
                raise ValueError("colisão de avaliação imutável") from None
    finally:
        temporario.unlink(missing_ok=True)
    return avaliacao_id


def rejeicoes_pendentes(
    lago: Path,
    *,
    escopo: str,
    identidade: str,
    entradas_digest: str,
    contrato: str,
) -> list[str]:
    """Aprovação sem referência/evidência não elimina uma rejeição conhecida."""
    avaliacoes: dict[str, dict[str, Any]] = {}
    for caminho in (lago / "estado/tse/validacoes").glob("*.json"):
        conteudo = caminho.read_bytes()
        if hashlib.sha256(conteudo).hexdigest() != caminho.stem:
            raise ValueError("integridade da avaliação divergente")
        dados = json.loads(conteudo)
        if all(
            dados.get(c) == v
            for c, v in {
                "escopo": escopo,
                "identidade": identidade,
                "entradas_digest": entradas_digest,
                "contrato": contrato,
            }.items()
        ):
            avaliacoes[caminho.stem] = dados
    superadas = {
        ref
        for a in avaliacoes.values()
        if a["resultado"] == "aprovada" and a.get("evidencia")
        for ref in a.get("superadas", [])
    }
    return sorted(
        i for i, a in avaliacoes.items() if a["resultado"] == "rejeitada" and i not in superadas
    )
