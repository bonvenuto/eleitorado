"""Competências, legislaturas e datas no fuso de Brasília."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

FUSO_BRASILIA = ZoneInfo("America/Sao_Paulo")


@dataclass(frozen=True)
class Competencia:
    rotulo: str
    data: date

    @classmethod
    def de_ano(cls, ano: int) -> Competencia:
        return cls(str(ano), date(ano, 1, 1))

    @classmethod
    def de_dia(cls, dia: date) -> Competencia:
        return cls(dia.isoformat(), dia)

    @classmethod
    def de_rotulo(cls, rotulo: str) -> Competencia:
        if len(rotulo) == 4 and rotulo.isdigit():
            return cls.de_ano(int(rotulo))
        return cls.de_dia(date.fromisoformat(rotulo))


def data_brasilia(instante: datetime) -> date:
    return instante.astimezone(FUSO_BRASILIA).date()


def legislatura_atual(dia: date) -> int:
    """A 57ª legislatura vai de 01/02/2023 a 31/01/2027 e a numeração muda a cada 4 anos."""
    ano_inicio = dia.year if (dia.month, dia.day) >= (2, 1) else dia.year - 1
    return 57 + (ano_inicio - 2023) // 4


def legislaturas(inicio: int, dia: date) -> list[int]:
    return list(range(inicio, legislatura_atual(dia) + 1))


def anos(inicio: int, dia: date) -> list[int]:
    return list(range(inicio, dia.year + 1))
