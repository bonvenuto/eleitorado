"""Decide quais (recurso, competência) estão com a coleta vencida."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from coletor.competencias import Competencia, anos
from coletor.manifesto import RecursoCompleto
from coletor.meta import HistoricoColetas

INTERVALO_DIAS = {"diaria": 1, "semanal": 7, "mensal": 30}


@dataclass(frozen=True)
class Tarefa:
    recurso: RecursoCompleto
    competencia: Competencia | None  # None: a competência é descoberta na coleta (CGU)


def _vencida(ultima: date | None, hoje: date, cadencia: str) -> bool:
    return ultima is None or (hoje - ultima).days >= INTERVALO_DIAS[cadencia]


def tarefa_snapshot(recurso: RecursoCompleto, hoje: date) -> Tarefa:
    if recurso.recurso.competencia.tipo == "data_arquivo":
        return Tarefa(recurso, None)
    return Tarefa(recurso, Competencia.de_dia(hoje))


def tarefas_pendentes(
    recursos: list[RecursoCompleto], historico: HistoricoColetas, hoje: date
) -> list[Tarefa]:
    tarefas: list[Tarefa] = []
    for rc in recursos:
        regra = rc.recurso
        if regra.publicacao == "snapshot":
            if _vencida(historico.ultima_data_sucesso(rc.id), hoje, regra.cadencia.corrente):
                tarefas.append(tarefa_snapshot(rc, hoje))
            continue
        assert regra.competencia.inicio is not None and regra.cadencia.anteriores is not None
        for ano in anos(regra.competencia.inicio, hoje):
            cadencia = regra.cadencia.corrente if ano == hoje.year else regra.cadencia.anteriores
            competencia = Competencia.de_ano(ano)
            if _vencida(historico.ultima_data_sucesso(rc.id, competencia.rotulo), hoje, cadencia):
                tarefas.append(Tarefa(rc, competencia))
    return tarefas
