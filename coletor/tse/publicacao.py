"""Publicação C2 por edição imutável e manifesto ao final, com controlador serializado.

A hipótese de serialização abrange listar/conferir/enviar e a validação causal privada.
Não há CAS ou exclusão remota. Falhas antes do PUT final conservam o manifesto anterior;
ACK ou GET incerto depois dele exige inspeção, sem rollback automático.
"""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from coletor.hashes import json_canonico
from coletor.publicacao import PREFIXO_C2, TIPOS, ErroPublicacao, Publicador, ResumoPublicacao
from coletor.tse.modelos import ReciboValidacaoTse, SelecaoTse
from coletor.tse.selecao import CONTRATO, conferir_recibo_tse

MANIFESTO = PREFIXO_C2 + "manifesto.json"
REGRA_PUBLICACAO = "tse:publicacao:v1"
MARTS_PUBLICOS = {
    "dim_candidatura.parquet": frozenset(
        {
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
        }
    ),
    "fct_receita_campanha_resumo.parquet": frozenset(
        {
            "candidatura_id",
            "natureza_recurso",
            "origem_recurso",
            "valor",
            "quantidade",
        }
    ),
    "fct_despesa_campanha_pj.parquet": frozenset(
        {
            "despesa_id",
            "candidatura_id",
            "tipo_fato",
            "fornecedor_cnpj",
            "data",
            "valor",
        }
    ),
    "fct_patrimonio_declarado.parquet": frozenset(
        {
            "candidatura_id",
            "tipo_bem_codigo",
            "quantidade",
            "valor",
        }
    ),
}


class ErroManifestoIncerto(ErroPublicacao):
    """PUT/GET final sem confirmação: o ponteiro pode já apontar a edição conferida."""

    def __init__(self, edicao_id: str):
        self.edicao_id = edicao_id
        self.manifesto = MANIFESTO
        super().__init__(
            f"resultado incerto do manifesto {MANIFESTO}; edição candidata {edicao_id}"
        )


def _lago_preparada(preparada: Path, recibo: ReciboValidacaoTse) -> Path:
    if not isinstance(recibo, ReciboValidacaoTse) or not isinstance(recibo.execucao_id, str):
        raise ValueError("recibo inválido")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", recibo.execucao_id):
        raise ValueError("identidade de execução inválida")
    preparada = Path(preparada)
    if ".." in preparada.parts:
        raise ValueError("caminho preparado não canônico")
    preparada = preparada.absolute()
    esperado = ("estado", "tse", "publicacoes", "preparadas", recibo.execucao_id, "marts")
    if preparada.parts[-6:] != esperado:
        raise ValueError("layout da saída preparada divergente")
    lago = preparada.parents[5]
    atual = lago
    for parte in esperado:
        atual /= parte
        if atual.is_symlink() or atual.is_junction():
            raise ValueError("caminho preparado simbólico ou junction")
    if lago.resolve() != lago or preparada.resolve() != preparada:
        raise ValueError("caminho preparado fora do lago canônico")
    return lago


def _arquivos_autorizados(preparada: Path) -> list[dict]:
    # O gate compartilhado já conferiu o hash deste selo contra o recibo persistido.
    # Os hashes usados no GET vêm do inventário autorizado, não de um hash novo livre.
    selo = json.loads((preparada.parent / "execucao.json").read_bytes())
    inventario = selo["saida"]
    if len(inventario) != len(MARTS_PUBLICOS) or {item["caminho"] for item in inventario} != set(
        MARTS_PUBLICOS
    ):
        raise ErroPublicacao("arquivos fora da allowlist pública C2 ou arquivo ausente")
    arquivos = []
    for item in inventario:
        caminho = preparada / item["caminho"]
        try:
            parquet = pq.ParquetFile(caminho)
            colunas = parquet.schema_arrow.names
            linhas = parquet.metadata.num_rows
        except (OSError, pa.ArrowException) as erro:
            raise ErroPublicacao(f"arquivo público inválido: {item['caminho']}") from erro
        if set(colunas) != MARTS_PUBLICOS[item["caminho"]] or len(colunas) != len(set(colunas)):
            raise ErroPublicacao(f"coluna fora da allowlist pública C2: {item['caminho']}")
        arquivos.append({**item, "linhas": linhas})
    return arquivos


def publicar_tse(
    publicador: Publicador,
    preparada: Path,
    selecao: SelecaoTse,
    gerado_em: datetime,
    versao: str,
    recibo: ReciboValidacaoTse,
) -> ResumoPublicacao:
    """Publica saída exata T7; repetir candidata antiga aprovada permite rollback explícito."""
    preparada = Path(preparada).absolute()
    lago = _lago_preparada(preparada, recibo)
    if not isinstance(gerado_em, datetime) or not isinstance(versao, str) or not versao.strip():
        raise ValueError("geração e versão das regras obrigatórias")
    conferir_recibo_tse(lago, selecao, recibo)
    arquivos = _arquivos_autorizados(preparada)
    regras = {"publicacao": REGRA_PUBLICACAO, "selecao": CONTRATO, "transformacao": versao}
    identidade = {
        "selecao": asdict(selecao),
        "selecao_digest": recibo.selecao_digest,
        "entradas_digest": recibo.entradas_digest,
        "saida_digest": recibo.saida_digest,
        "saida": [{k: a[k] for k in ("caminho", "tamanho", "sha256")} for a in arquivos],
        "regras": regras,
    }
    edicao_id = hashlib.sha256(json_canonico(identidade).encode("utf-8")).hexdigest()
    prefixo = f"{PREFIXO_C2}edicoes/{edicao_id}/"
    esperadas = {prefixo + item["caminho"] for item in arquivos}
    anteriores = publicador.listar()
    if any(c.startswith(prefixo) and c not in esperadas for c in anteriores):
        raise ErroPublicacao("colisão de edição imutável: objeto extra no prefixo")
    faltantes = []
    # Colisões são verificadas antes de qualquer envio; objetos existentes não são sobrescritos.
    for item in arquivos:
        chave = prefixo + item["caminho"]
        if chave in anteriores:
            if not publicador.conferir(chave, item["sha256"], item["tamanho"]):
                raise ErroPublicacao(f"colisão de edição imutável: {chave}")
        else:
            faltantes.append(item)
    for item in faltantes:
        chave = prefixo + item["caminho"]
        publicador.enviar(preparada / item["caminho"], chave, TIPOS[".parquet"])
        if not publicador.conferir(chave, item["sha256"], item["tamanho"]):
            raise ErroPublicacao(f"conferência de bytes remotos falhou: {chave}")
    # Rechecagem causal e física imediatamente antes de publicar o ponteiro mutável.
    conferir_recibo_tse(lago, selecao, recibo)
    manifesto = {
        "protocolo": REGRA_PUBLICACAO,
        "edicao_id": edicao_id,
        "gerado_em": gerado_em.isoformat(),
        "versao": versao,
        "regras": regras,
        "selecao_id": selecao.selecao_id,
        "versoes_tse": dict(sorted(selecao.versoes.items())),
        "selecao_digest": recibo.selecao_digest,
        "entradas_digest": recibo.entradas_digest,
        "saida_digest": recibo.saida_digest,
        "arquivos": [
            {
                "caminho": prefixo + a["caminho"],
                "bytes": a["tamanho"],
                "sha256": a["sha256"],
                "linhas": a["linhas"],
            }
            for a in arquivos
        ],
    }
    conteudo = json_canonico(manifesto).encode("utf-8")
    with tempfile.TemporaryDirectory(prefix="tse-manifesto-") as pasta:
        caminho = Path(pasta) / "manifesto.json"
        caminho.write_bytes(conteudo)
        try:
            publicador.enviar(caminho, MANIFESTO, TIPOS[".json"])
            if not publicador.conferir(
                MANIFESTO, hashlib.sha256(conteudo).hexdigest(), len(conteudo)
            ):
                raise ErroPublicacao("GET do manifesto não confirmou o conteúdo enviado")
        except Exception as erro:
            raise ErroManifestoIncerto(edicao_id) from erro
    return ResumoPublicacao(len(faltantes) + 1, 0)
