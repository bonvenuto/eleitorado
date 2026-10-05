"""Decide quais (recurso, competência) estão com a coleta vencida."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from coletor.competencias import Competencia, anos, meses
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
        do_recurso: list[Tarefa] = []
        if regra.competencia.tipo == "mes":
            corrente = date(hoje.year, hoje.month, 1)
            anterior = date(corrente.year - (corrente.month == 1), (corrente.month - 2) % 12 + 1, 1)
            ultimo = corrente
            if regra.competencia.fim:
                ultimo = min(ultimo, Competencia.de_rotulo(regra.competencia.fim).data)
            for dia in meses(date(regra.competencia.inicio, 1, 1), ultimo):
                cadencia = regra.cadencia.corrente if dia >= anterior else regra.cadencia.anteriores
                competencia = Competencia.de_mes(dia.year, dia.month)
                if _vencida(
                    historico.ultima_data_sucesso(rc.id, competencia.rotulo), hoje, cadencia
                ):
                    do_recurso.append(Tarefa(rc, competencia))
        else:
            for ano in anos(regra.competencia.inicio, hoje):
                cadencia = (
                    regra.cadencia.corrente if ano == hoje.year else regra.cadencia.anteriores
                )
                competencia = Competencia.de_ano(ano)
                if _vencida(
                    historico.ultima_data_sucesso(rc.id, competencia.rotulo), hoje, cadencia
                ):
                    do_recurso.append(Tarefa(rc, competencia))
        if regra.limite_por_execucao is not None:
            do_recurso = sorted(do_recurso, key=lambda t: t.competencia.data, reverse=True)
            do_recurso = do_recurso[: regra.limite_por_execucao]
        tarefas.extend(do_recurso)
    return tarefas
