"""Execução de uma lista de tarefas, com registro em `meta`."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from coletor.agenda import Tarefa
from coletor.coleta import Dependencias, coletar
from coletor.dbt import ResultadoDbt
from coletor.meta import HistoricoColetas, RegistroColeta, RegistroExecucao, RepositorioMeta

log = logging.getLogger(__name__)


@dataclass
class ResumoColetas:
    carregadas: int = 0
    sem_alteracao: int = 0
    nao_publicadas: int = 0
    falhas: int = 0

    def contar(self, status: str) -> None:
        if status == "carregada":
            self.carregadas += 1
        elif status == "sem_alteracao":
            self.sem_alteracao += 1
        elif status == "nao_publicada":
            self.nao_publicadas += 1
        else:
            self.falhas += 1

    @property
    def sucesso(self) -> bool:
        return self.falhas == 0


def _registrar_com_retentativa(repositorio: RepositorioMeta, registro: RegistroColeta) -> bool:
    for tentativa in (1, 2):
        try:
            repositorio.registrar_coleta(registro)
            return True
        except Exception:  # noqa: BLE001 - a falha em meta não pode parar as demais coletas
            log.exception(
                "falha ao gravar %s em meta.coletas (tentativa %d)", registro.coleta_id, tentativa
            )
    return False


def rodar(
    tarefas: list[Tarefa],
    historico: HistoricoColetas,
    deps: Dependencias,
    repositorio: RepositorioMeta,
    execucao_id: str,
    forcar: bool = False,
) -> ResumoColetas:
    resumo = ResumoColetas()
    for tarefa in tarefas:
        registro = coletar(tarefa.recurso, tarefa.competencia, historico, deps, execucao_id, forcar)
        historico.registrar(registro)
        if _registrar_com_retentativa(repositorio, registro):
            resumo.contar(registro.status)
        else:
            resumo.contar("falha")
        log.info(
            "%s competencia=%s status=%s linhas=%s%s",
            registro.recurso_id,
            registro.competencia,
            registro.status,
            registro.linhas,
            f" erro={registro.erro}" if registro.erro else "",
        )
    return resumo


def registro_execucao(
    execucao_id: str,
    origem: str,
    deps: Dependencias,
    inicio: datetime,
    resumo: ResumoColetas,
    dbt: ResultadoDbt | None = None,
) -> RegistroExecucao:
    sucesso = resumo.sucesso and (dbt is None or dbt.status == "sucesso")
    return RegistroExecucao(
        execucao_id=execucao_id,
        origem=origem,
        iniciada_em=inicio,
        finalizada_em=deps.agora(),
        status="sucesso" if sucesso else "falha",
        coletas_carregadas=resumo.carregadas,
        coletas_sem_alteracao=resumo.sem_alteracao,
        coletas_nao_publicadas=resumo.nao_publicadas,
        coletas_falha=resumo.falhas,
        versao=deps.config.versao,
        dbt_status=dbt.status if dbt else None,
        dbt_testes_com_erro=dbt.testes_com_erro if dbt else None,
    )
