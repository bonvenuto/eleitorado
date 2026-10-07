"""Despacho TSE: um ZIP por versão, sem substituir partições do lago."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from coletor.adaptadores import tse_zip
from coletor.adaptadores.base import ErroColeta
from coletor.competencias import Competencia, data_brasilia
from coletor.conversao import Controle
from coletor.hashes import json_canonico
from coletor.http import ErroHttp
from coletor.manifesto import RecursoCompleto
from coletor.meta import HistoricoColetas, RegistroColeta
from coletor.tse.originais import arquivar_original
from coletor.tse.validacoes import gravar_avaliacao, rejeicoes_pendentes
from coletor.tse.versoes import gravar_versao, id_versao

if TYPE_CHECKING:
    from coletor.coleta import Dependencias


def coletar_tse(
    recurso: RecursoCompleto,
    competencia: Competencia | None,
    historico: HistoricoColetas,
    deps: Dependencias,
    execucao_id: str,
    forcar: bool = False,
) -> RegistroColeta:
    """Revalida todas as famílias, inclusive ao repetir ou forçar o mesmo ZIP."""
    inicio = deps.agora()
    registro = RegistroColeta.novo(execucao_id, recurso, competencia, inicio, deps.config.versao)
    with tempfile.TemporaryDirectory(prefix="coletor-tse-") as temporario:
        pasta = Path(temporario)
        try:
            extracao = tse_zip.extrair(
                recurso.recurso, competencia, pasta, deps.http, data_brasilia(inicio)
            )
            registro.definir_competencia(extracao.competencia)
            registro.url = extracao.url
            registro.parametros = dict(extracao.parametros)
            registro.http_status = extracao.http_status
            registro.http_last_modified = extracao.last_modified
            registro.http_etag = extracao.etag
            registro.bytes_arquivo = extracao.bytes_arquivo
            registro.sha256_arquivo = extracao.sha256_arquivo
            versao_id = id_versao(recurso, extracao)
            registro.arquivo_original = arquivar_original(
                deps.config.lago, recurso, extracao, deps.armazenamento, deps.config.prefixo_gcs
            )
            contrato = "tse:estrutura:v1"
            entradas_digest = hashlib.sha256(
                json_canonico(
                    {
                        "recurso_id": recurso.id,
                        "ano": extracao.competencia.data.year,
                        "sha256_zip": extracao.sha256_arquivo,
                        "layouts": {
                            f: f"tse:{f}:{extracao.competencia.data.year}:v1"
                            for f in recurso.recurso.familias
                        },
                        "membros": recurso.recurso.familias,
                    }
                ).encode()
            ).hexdigest()
            try:
                familias = tse_zip.preparar_familias(
                    recurso.recurso, extracao.competencia, extracao.arquivo_original, pasta
                )
            except ErroColeta as erro:
                gravar_avaliacao(
                    deps.config.lago,
                    escopo="versao",
                    identidade=versao_id,
                    entradas_digest=entradas_digest,
                    contrato=contrato,
                    execucao_id=execucao_id,
                    resultado="rejeitada",
                    motivos=[{"codigo": "zip_layout_invalido", "detalhe": str(erro)}],
                    evidencia=registro.arquivo_original,
                )
                raise
            if rejeicoes_pendentes(
                deps.config.lago,
                escopo="versao",
                identidade=versao_id,
                entradas_digest=entradas_digest,
                contrato=contrato,
            ):
                raise ErroColeta("versão possui rejeição estrutural pendente de decisão explícita")
            descritor = deps.config.lago / "estado/tse/versoes" / f"{versao_id}.json"
            repetida = descritor.exists()
            controle = Controle(
                registro.coleta_id,
                extracao.competencia.rotulo,
                extracao.competencia.data,
                registro.arquivo_original,
                deps.agora(),
            )
            versao = gravar_versao(deps.config.lago, recurso, extracao, familias, controle)
            registro.sha256_conteudo = versao.sha256_semantico
            registro.parametros.update(
                {
                    "versao_id": versao.versao_id,
                    "familias": versao.familias,
                    "layouts": versao.layouts,
                }
            )
            registro.arquivo_carga = descritor.relative_to(deps.config.lago).as_posix()
            registro.linhas = sum(
                json.loads(descritor.read_text(encoding="utf-8"))["contagens"].values()
            )
            return registro.finalizar("sem_alteracao" if repetida else "carregada", deps.agora())
        except Exception as erro:  # noqa: BLE001 - falha registrada sem interromper outros recursos
            registro.erro = f"{type(erro).__name__}: {erro}"
            if isinstance(erro, ErroHttp):
                registro.http_status = erro.status
            return registro.finalizar("falha", deps.agora())
