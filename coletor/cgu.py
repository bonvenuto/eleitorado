"""Descoberta da data do arquivo mais recente nas páginas de download da CGU."""

from __future__ import annotations

import re
from datetime import date, timedelta

_PADRAO = re.compile(
    r'arquivos\.push\(\s*\{\s*"ano"\s*:\s*"(\d{4})"\s*,\s*"mes"\s*:\s*"(\d{2})"'
    r'\s*,\s*"dia"\s*:\s*"(\d{2})"'
)


def descobrir_data(html: str) -> date | None:
    datas = [date(int(ano), int(mes), int(dia)) for ano, mes, dia in _PADRAO.findall(html)]
    return max(datas) if datas else None


def datas_candidatas(descoberta: date | None, hoje: date) -> list[date]:
    """Data anunciada na página primeiro; depois D-1, D-2 e D-3."""
    candidatas = [descoberta] if descoberta else []
    for dias in (1, 2, 3):
        dia = hoje - timedelta(days=dias)
        if dia not in candidatas:
            candidatas.append(dia)
    return candidatas
