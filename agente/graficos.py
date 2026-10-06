"""Gráficos do relatório: especificações Vega-Lite e o grafo de relações em SVG.

O agente escolhe o tipo e aponta a consulta; aqui saem as especificações com cores e
acessibilidade padronizadas. Os dados entram na própria especificação (o HTML é autocontido).
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime
from decimal import Decimal
from html import escape
from typing import Any

import pyarrow as pa

from agente.modelos import Grafico

MAXIMO_LINHAS = 5000
COR = "#2563eb"
COR_DESTAQUE = "#dc2626"
PADRAO_CPF = re.compile(r"(?<!\d)\d{3}\.?(\d{3})\.?(\d{3})-?\d{2}(?!\d)")


def mascarar(texto: str) -> str:
    """Mascara CPFs (11 dígitos, com ou sem pontuação) como nos marts: ***.456.789-**."""
    return PADRAO_CPF.sub(r"***.\1.\2-**", texto)


def _valor(valor: Any) -> Any:
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, datetime | date):
        return valor.isoformat()
    if isinstance(valor, str):
        return mascarar(valor)
    if isinstance(valor, float) and math.isnan(valor):
        return None
    return valor


def linhas(tabela: pa.Table, limite: int = MAXIMO_LINHAS) -> list[dict[str, Any]]:
    """Linhas da consulta prontas para o HTML: números como float, datas em ISO, CPF mascarado."""
    return [
        {chave: _valor(valor) for chave, valor in linha.items()}
        for linha in tabela.slice(0, limite).to_pylist()
    ]


def _tipo_campo(tabela: pa.Table, coluna: str) -> str:
    tipo = tabela.schema.field(coluna).type
    if pa.types.is_temporal(tipo):
        return "temporal"
    if pa.types.is_integer(tipo) or pa.types.is_floating(tipo) or pa.types.is_decimal(tipo):
        return "quantitative"
    return "nominal"


def _exigir_colunas(grafico: Grafico, tabela: pa.Table) -> None:
    campos = [grafico.x, grafico.y, grafico.cor, grafico.origem, grafico.destino, grafico.peso]
    faltando = [c for c in campos if c and c not in tabela.column_names]
    if faltando:
        raise ValueError(
            f"gráfico '{grafico.titulo}': colunas {faltando} não existem em {grafico.consulta}"
        )


def especificacao(grafico: Grafico, tabela: pa.Table) -> dict[str, Any]:
    """Vega-Lite para barras, linha, dispersão e distribuição."""
    _exigir_colunas(grafico, tabela)
    base: dict[str, Any] = {
        "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
        "description": mascarar(grafico.titulo),
        "data": {"values": linhas(tabela)},
        "width": "container",
        "height": 320,
        "config": {
            "background": None,
            "font": "system-ui, sans-serif",
            "axis": {"labelColor": "#64748b", "titleColor": "#64748b", "gridColor": "#e2e8f0"},
            "legend": {"labelColor": "#64748b", "titleColor": "#64748b"},
        },
    }
    x, y = grafico.x, grafico.y
    cor: dict[str, Any] = {"value": COR}
    if grafico.cor:
        cor = {"field": grafico.cor, "type": "nominal"}
    elif grafico.destaque is not None and x:
        destaque = grafico.destaque.replace("\\", "\\\\").replace("'", "\\'")
        cor = {
            "condition": {"test": f"datum['{x}'] == '{destaque}'", "value": COR_DESTAQUE},
            "value": COR,
        }
    dica = [{"field": c, "type": _tipo_campo(tabela, c)} for c in (x, y, grafico.cor) if c]
    if grafico.tipo == "barras":
        assert x and y
        base |= {
            "mark": {"type": "bar", "cornerRadiusEnd": 2},
            "height": {"step": 22},
            "encoding": {
                "y": {"field": x, "type": "nominal", "sort": "-x", "title": None},
                "x": {"field": y, "type": "quantitative"},
                "color": cor,
                "tooltip": dica,
            },
        }
    elif grafico.tipo == "linha":
        assert x and y
        base |= {
            "mark": {"type": "line", "point": True},
            "encoding": {
                "x": {"field": x, "type": _tipo_campo(tabela, x)},
                "y": {"field": y, "type": "quantitative"},
                "color": cor if grafico.cor else {"value": COR},
                "tooltip": dica,
            },
        }
    elif grafico.tipo == "dispersao":
        assert x and y
        base |= {
            "mark": {"type": "circle", "opacity": 0.7},
            "encoding": {
                "x": {"field": x, "type": _tipo_campo(tabela, x)},
                "y": {"field": y, "type": "quantitative"},
                "color": cor,
                "tooltip": dica,
            },
        }
    elif grafico.tipo == "distribuicao":
        assert x
        base |= {
            "mark": "bar",
            "encoding": {
                "x": {"field": x, "bin": {"maxbins": 40}, "type": "quantitative"},
                "y": {"aggregate": "count", "title": "quantidade"},
                "color": {"value": COR},
            },
        }
    else:
        raise ValueError(f"tipo sem Vega-Lite: {grafico.tipo}")
    return base


def rede_svg(grafico: Grafico, tabela: pa.Table, largura: int = 760) -> str:
    """Grafo bipartido: origens à esquerda, destinos à direita, ligações com espessura pelo peso."""
    _exigir_colunas(grafico, tabela)
    assert grafico.origem and grafico.destino
    dados = linhas(tabela, 200)
    origens = list(dict.fromkeys(str(d[grafico.origem]) for d in dados))[:25]
    destinos = list(dict.fromkeys(str(d[grafico.destino]) for d in dados))[:25]
    altura = 40 + 28 * max(len(origens), len(destinos), 1)

    def posicao(lista: list[str], nome: str) -> float:
        return 30 + (altura - 60) * (lista.index(nome) + 0.5) / max(len(lista), 1)

    pesos = [
        float(d[grafico.peso] or 0) for d in dados if grafico.peso and d[grafico.peso] is not None
    ]
    maximo = max(pesos) if pesos else 1.0
    partes = [
        f'<svg class="rede" viewBox="0 0 {largura} {altura}" role="img" '
        f'aria-label="{escape(grafico.titulo)}">'
    ]
    x1, x2 = 230, largura - 230
    for d in dados:
        origem, destino = str(d[grafico.origem]), str(d[grafico.destino])
        if origem not in origens or destino not in destinos:
            continue
        peso = float(d[grafico.peso] or 0) if grafico.peso else 1.0
        espessura = 1 + 7 * (peso / maximo if maximo else 0)
        titulo = escape(f"{origem} → {destino}" + (f": {peso:,.2f}" if grafico.peso else ""))
        partes.append(
            f'<line x1="{x1}" y1="{posicao(origens, origem):.1f}" x2="{x2}" '
            f'y2="{posicao(destinos, destino):.1f}" stroke-width="{espessura:.1f}">'
            f"<title>{titulo}</title></line>"
        )
    for nome in origens:
        y = posicao(origens, nome)
        partes.append(f'<circle cx="{x1}" cy="{y:.1f}" r="5"/>')
        partes.append(
            f'<text x="{x1 - 10}" y="{y + 4:.1f}" text-anchor="end">{escape(nome[:34])}</text>'
        )
    for nome in destinos:
        y = posicao(destinos, nome)
        partes.append(f'<circle cx="{x2}" cy="{y:.1f}" r="5"/>')
        partes.append(f'<text x="{x2 + 10}" y="{y + 4:.1f}">{escape(nome[:34])}</text>')
    partes.append("</svg>")
    return "".join(partes)
