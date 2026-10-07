"""Fluxo de uma coleta: extrair, deduplicar, arquivar, converter, carregar e registrar."""

from __future__ import annotations

import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from coletor.adaptadores import adaptador_para
from coletor.adaptadores.base import Preparado
from coletor.armazenamento import Armazenamento, caminho_de_uri, caminho_original
from coletor.competencias import Competencia, data_brasilia
from coletor.config import Config
from coletor.conversao import Controle, csv_para_parquet, registros_para_parquet
from coletor.hashes import sha256_arquivo
from coletor.http import ClienteHttp, ErroHttp
from coletor.lago import Particionamento, Warehouse
from coletor.manifesto import Recurso, RecursoCompleto
from coletor.meta import HistoricoColetas, RegistroColeta

EXPIRACAO_SNAPSHOT_DIAS = 60


@dataclass
class Dependencias:
    config: Config
    http: ClienteHttp
    armazenamento: Armazenamento
    warehouse: Warehouse
    agora: Callable[[], datetime]
    dormir: Callable[[float], None] = time.sleep


def particionamento(recurso: Recurso, destino: str) -> Particionamento:
    if recurso.adaptador == "webdav_zip":
        return Particionamento("MONTH")  # recorte mensal da Receita: o histórico fica, sem expirar
    if recurso.publicacao == "snapshot":
        return Particionamento("DAY", EXPIRACAO_SNAPSHOT_DIAS if destino == "raw" else None)
    if recurso.competencia.tipo == "dia":
        return Particionamento("DAY")  # por competência diária: sem expiração
    return Particionamento("MONTH" if recurso.competencia.tipo == "mes" else "YEAR")


def tabela_destino(recurso: RecursoCompleto, destino: str) -> str:
    """Pasta no lago: `raw/<órgão>/<recurso>`, ou `replay/raw/...` na reconstrução."""
    raiz = "replay/raw" if destino == "replay" else "raw"
    return f"{raiz}/{recurso.orgao}/{recurso.recurso.id}"


def nao_publicada(
    recurso: Recurso, competencia: Competencia | None, erro: ErroHttp, hoje: date
) -> bool:
    """A fonte ainda não publicou a competência.

    Ano: HTTP 404 no ano corrente, no 1º trimestre. Mês: HTTP 403 ou 404 nos três meses mais
    recentes (o Portal da Transparência gera os arquivos mensais com semanas de atraso).
    """
    if recurso.publicacao != "por_competencia" or competencia is None:
        return False
    if recurso.competencia.tipo == "mes":
        tres_meses = date(hoje.year, hoje.month, 1)
        for _ in range(2):
            tres_meses = date(
                tres_meses.year - (tres_meses.month == 1), (tres_meses.month - 2) % 12 + 1, 1
            )
        return erro.status in (403, 404) and competencia.data >= tres_meses
    return erro.status == 404 and competencia.data.year == hoje.year and hoje.month <= 3


def _descrever(erro: Exception) -> str:
    return f"{type(erro).__name__}: {erro}"


def _converter_e_carregar(
    recurso: RecursoCompleto,
    competencia: Competencia,
    uri_original: str,
    preparado: Preparado,
    registro: RegistroColeta,
    historico: HistoricoColetas,
    deps: Dependencias,
    pasta: Path,
    destino: str,
) -> None:
    controle = Controle(
        registro.coleta_id, competencia.rotulo, competencia.data, uri_original, deps.agora()
    )
    parquet = pasta / "carga.parquet"
    if preparado.csv is not None:
        resultado = csv_para_parquet(preparado.csv, parquet, recurso.recurso.formato, controle)
    else:
        resultado = registros_para_parquet(preparado.registros or [], parquet, controle)
    carga = deps.warehouse.carregar_parquet(
        tabela_destino(recurso, destino),
        parquet,
        particionamento(recurso.recurso, destino),
        competencia.data,
        registro.coleta_id,
    )
    registro.arquivo_carga = carga.caminho
    registro.linhas = carga.linhas
    registro.colunas = resultado.colunas
    referencia = historico.colunas_referencia(recurso.id, competencia)
    registro.esquema_alterado = referencia is not None and [o for o, _ in referencia] != [
        o for o, _ in resultado.colunas
    ]


def coletar(
    recurso: RecursoCompleto,
    competencia: Competencia | None,
    historico: HistoricoColetas,
    deps: Dependencias,
    execucao_id: str,
    forcar: bool = False,
) -> RegistroColeta:
    inicio = deps.agora()
    hoje = data_brasilia(inicio)
    registro = RegistroColeta.novo(
        execucao_id, recurso, competencia, inicio, deps.config.versao, destino="raw"
    )
    adaptador = adaptador_para(recurso.recurso)
    with tempfile.TemporaryDirectory(prefix="coletor-") as temporario:
        pasta = Path(temporario)
        try:
            # fonte que informa a competência disponível: a já coletada não é baixada de novo
            disponivel = getattr(adaptador, "competencia_disponivel", None)
            if competencia is None and disponivel is not None:
                competencia = disponivel(recurso.recurso, deps.http)
                registro.definir_competencia(competencia)
                anterior = historico.ultimo_sha(recurso.id, competencia.rotulo)
                if not forcar and anterior is not None:
                    registro.sha256_conteudo = anterior
                    return registro.finalizar("sem_alteracao", deps.agora())
            extracao = adaptador.extrair(recurso.recurso, competencia, pasta, deps.http, hoje)
            registro.definir_competencia(extracao.competencia)
            registro.url = extracao.url
            registro.parametros = extracao.parametros
            registro.http_status = extracao.http_status
            registro.http_last_modified = extracao.last_modified
            registro.http_etag = extracao.etag
            registro.bytes_arquivo = extracao.bytes_arquivo
            registro.sha256_arquivo = extracao.sha256_arquivo
            preparado = adaptador.preparar(
                recurso.recurso, extracao.competencia, extracao.arquivo_original, pasta
            )
            registro.sha256_conteudo = preparado.sha256_conteudo
            anterior = historico.ultimo_sha(recurso.id, extracao.competencia.rotulo)
            if not forcar and anterior == preparado.sha256_conteudo:
                return registro.finalizar("sem_alteracao", deps.agora())
            caminho = caminho_original(
                deps.config.prefixo_gcs,
                recurso.orgao,
                recurso.recurso.id,
                extracao.competencia.rotulo,
                inicio,
                preparado.sha256_conteudo,
                extracao.extensao,
            )
            registro.arquivo_original = deps.armazenamento.enviar(
                extracao.arquivo_original, caminho
            )
            _converter_e_carregar(
                recurso,
                extracao.competencia,
                registro.arquivo_original,
                preparado,
                registro,
                historico,
                deps,
                pasta,
                "raw",
            )
            return registro.finalizar("carregada", deps.agora())
        except ErroHttp as erro:
            registro.erro = _descrever(erro)
            registro.http_status = erro.status
            if erro.status in (405, 429):
                status = (
                    "adiada"  # bloqueio temporário da fonte (anti-robô ou limite de requisições)
                )
            elif nao_publicada(recurso.recurso, competencia, erro, hoje):
                status = "nao_publicada"
            else:
                status = "falha"
            return registro.finalizar(status, deps.agora())

        except Exception as erro:  # noqa: BLE001 - toda falha vira registro e as demais seguem
            registro.erro = _descrever(erro)
            return registro.finalizar("falha", deps.agora())


def recarregar(
    recurso: RecursoCompleto,
    competencia: Competencia,
    uri_original: str,
    historico: HistoricoColetas,
    deps: Dependencias,
    execucao_id: str,
    destino: str,
) -> RegistroColeta:
    inicio = deps.agora()
    registro = RegistroColeta.novo(
        execucao_id, recurso, competencia, inicio, deps.config.versao, destino=destino
    )
    registro.url = uri_original
    registro.parametros = {"recarga_de": uri_original}
    registro.arquivo_original = uri_original
    adaptador = adaptador_para(recurso.recurso)
    with tempfile.TemporaryDirectory(prefix="coletor-") as temporario:
        pasta = Path(temporario)
        try:
            extensao = uri_original.rsplit("/", 1)[-1].split(".", 1)[1]
            original = pasta / f"original.{extensao}"
            deps.armazenamento.baixar(caminho_de_uri(uri_original), original)
            registro.bytes_arquivo = original.stat().st_size
            registro.sha256_arquivo = sha256_arquivo(original)
            preparado = adaptador.preparar(recurso.recurso, competencia, original, pasta)
            registro.sha256_conteudo = preparado.sha256_conteudo
            _converter_e_carregar(
                recurso,
                competencia,
                uri_original,
                preparado,
                registro,
                historico,
                deps,
                pasta,
                destino,
            )
            return registro.finalizar("recarregada", deps.agora())
        except Exception as erro:  # noqa: BLE001
            registro.erro = _descrever(erro)
            return registro.finalizar("falha", deps.agora())
