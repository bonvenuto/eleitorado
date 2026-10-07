"""Preparo privado imutável: um vetor explícito de arquivos por execução dbt."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from coletor.esquemas import carregar_esquemas, garantir_fontes
from coletor.hashes import json_canonico
from coletor.tse.durabilidade import conferir_recuperacao, gravar_json
from coletor.tse.evidencias import PROTOCOLO_PREPARACAO
from coletor.tse.modelos import SelecaoTse
from coletor.tse.selecao import (
    CONTRATO,
    digest_entradas,
    digest_selecao,
    inventario_entradas,
    validar_selecao,
    vars_selecao,
)


@dataclass(frozen=True)
class ExecucaoTse:
    selecao_id: str | None
    vars_dbt: dict
    saida: Path
    publicavel: bool


def preparar_execucao_tse(
    lago: Path, execucao_id: str, target: str, selecao: SelecaoTse | None = None
) -> ExecucaoTse:
    """Fixa o vigente uma vez; candidato explícito não consulta nem promove o vigente.

    Ausência de inicialização permite somente bootstrap não publicável. O controlador
    transporta vars_dbt como JSON integral em rodar_dbt(..., argumentos=['--vars', json]).
    """
    conferir_recuperacao(lago)
    if not isinstance(execucao_id, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", execucao_id
    ):
        raise ValueError("identidade de execução inválida")
    lago = lago.resolve()
    pasta = lago / "estado/tse/publicacoes/preparadas" / execucao_id
    if not pasta.resolve().is_relative_to(lago):
        raise ValueError("saída fora do lago")
    if selecao is None:
        vigente = lago / "estado/tse/vigente.json"
        try:
            dados = json.loads(vigente.read_bytes())
        except FileNotFoundError:
            if (lago / "estado/tse/inicializado.json").exists():
                raise ValueError("TSE inicializado sem seleção vigente") from None
        else:
            if not isinstance(dados, dict) or set(dados) != {"selecao_id", "versoes"}:
                raise ValueError("seletor TSE inválido")
            selecao = SelecaoTse(**dados)
    if selecao is not None:
        impedimentos = validar_selecao(lago, selecao)
        if impedimentos:
            raise ValueError("seleção TSE inválida: " + "; ".join(impedimentos))
        variaveis = vars_selecao(lago, selecao, execucao_id)
        entradas = inventario_entradas(lago, selecao)
        entradas_digest = digest_entradas(lago, selecao)
        selecao_digest = digest_selecao(selecao)
    else:
        projeto = Path(__file__).resolve().parents[2] / "dbt"
        esquemas = {
            chave: colunas
            for chave, colunas in carregar_esquemas(projeto).items()
            if chave.startswith("estado/tse/ci/")
        }
        garantir_fontes(lago, esquemas)
        variaveis = {
            "tse_fontes": {
                chave.rsplit("/", 1)[1]: [(lago / chave / "vazio/vazio.parquet").as_posix()]
                for chave in esquemas
            },
            "tse_saida": (pasta / "marts").as_posix(),
        }
        variaveis["tse_proveniencia"] = {
            caminho: {"ano_arquivo": None, "versao_id": None, "layout_id": None}
            for caminhos in variaveis["tse_fontes"].values()
            for caminho in caminhos
        }
        entradas, entradas_digest, selecao_digest = {}, None, None
    # A pasta exclusiva impede reuso de saída, preparação ou artefatos de outra invocação.
    pasta.parent.mkdir(parents=True, exist_ok=True)
    pasta.mkdir()
    saida = pasta / "marts"
    saida.mkdir()
    gravar_json(
        pasta / "preparacao.json",
        {
            "protocolo": PROTOCOLO_PREPARACAO,
            "execucao_id": execucao_id,
            "target": target,
            "selecao": asdict(selecao) if selecao else None,
            "selecao_digest": selecao_digest,
            "entradas": entradas,
            "entradas_digest": entradas_digest,
            "vars": variaveis,
            "vars_digest": hashlib.sha256(json_canonico(variaveis).encode("utf-8")).hexdigest(),
            "saida": saida.relative_to(lago).as_posix(),
            "contrato": CONTRATO,
        },
    )
    return ExecucaoTse(
        selecao.selecao_id if selecao else None, variaveis, saida, selecao is not None
    )
