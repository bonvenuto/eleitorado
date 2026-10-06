"""Relatório da investigação: relatorio.json (validado) e relatorio.html (autocontido).

O HTML abre sem internet (Vega, Vega-Lite e vega-embed embutidos), escapa todo conteúdo vindo
dos dados e da web e mascara CPFs em qualquer texto.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup

from agente import graficos
from agente.diario import Diario
from agente.modelos import Estado, RegistroAchado, Veredito

PASTA_HTML = Path(__file__).resolve().parent / "html"
PASTA_ESTATICOS = Path(__file__).resolve().parent / "estaticos"
SCRIPTS = ("vega.min.js", "vega-lite.min.js", "vega-embed.min.js")


class ErroRelatorio(Exception):
    """O relatório não cumpre as regras de evidência; nada é gerado."""


def confianca(veredito: Veredito) -> str:
    """Alta: confirmado e corroborado por fonte independente; média: confirmado só com os dados."""
    return "alta" if veredito.corroboracao_independente else "média"


def _consultas_do_registro(registro: RegistroAchado) -> set[str]:
    citadas = set(registro.achado.consultas_citadas())
    for veredito in registro.vereditos:
        for alternativa in veredito.alternativas:
            citadas |= set(alternativa.consultas)
    for correlacionado in registro.correlacionados:
        citadas |= set(correlacionado.consultas)
    return citadas


def resumo_ciclos(arquivo: Path) -> list[dict[str, Any]]:
    """Linha do tempo: uma entrada por sessão (fase, alvo e agente consecutivos)."""
    if not arquivo.exists():
        return []
    sessoes: list[dict[str, Any]] = []
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        passo = json.loads(linha)
        chave = (passo["fase"], passo["alvo"], passo["agente"])
        if not sessoes or sessoes[-1]["chave"] != chave:
            sessoes.append(
                {
                    "chave": chave,
                    "fase": passo["fase"],
                    "alvo": passo["alvo"],
                    "agente": passo["agente"],
                    "inicio": passo["em"],
                    "etapas": Counter(),
                    "ferramentas": Counter(),
                }
            )
        sessao = sessoes[-1]
        sessao["etapas"][passo["etapa"]] += 1
        if passo.get("ferramenta"):
            sessao["ferramentas"][passo["ferramenta"].removeprefix("mcp__agente__")] += 1
    return [
        {
            "fase": s["fase"],
            "alvo": s["alvo"],
            "agente": s["agente"],
            "inicio": s["inicio"],
            "think": s["etapas"]["think"],
            "act": s["etapas"]["act"],
            "sense": s["etapas"]["sense"],
            "ferramentas": dict(s["ferramentas"]),
        }
        for s in sessoes
    ]


def montar(estado: Estado, pasta: Path, gerado_em: datetime) -> dict[str, Any]:
    diario = Diario(pasta)
    por_situacao: dict[str, list[dict[str, Any]]] = {
        "confirmado": [],
        "inconclusivo": [],
        "descartado": [],
    }
    for registro in estado.achados:
        destino = "inconclusivo" if registro.situacao == "em_validacao" else registro.situacao
        por_situacao[destino].append(registro.model_dump(mode="json"))
    hipoteses_descartadas = [
        h.model_dump(mode="json")
        for h in estado.hipoteses
        if h.situacao == "descartada"
        and not any(r.achado.hipotese_id == h.id for r in estado.achados)
    ]
    return {
        "id": estado.id,
        "tema": estado.tema,
        "criada_em": estado.criada_em.isoformat(),
        "gerado_em": gerado_em.isoformat(timespec="seconds"),
        "situacao": estado.situacao,
        "motivo_parada": estado.motivo_parada,
        "versao_dados": estado.versao_dados,
        "uso": estado.uso.model_dump(),
        "resumo": estado.resumo.model_dump(mode="json") if estado.resumo else None,
        "achados": por_situacao["confirmado"],
        "inconclusivos": por_situacao["inconclusivo"],
        "descartados": por_situacao["descartado"],
        "hipoteses_descartadas": hipoteses_descartadas,
        "hipoteses": [h.model_dump(mode="json") for h in estado.hipoteses],
        "consultas": {c.id: c.__dict__ for c in diario.consultas().values()},
        "ciclos": resumo_ciclos(pasta / "ciclos.jsonl"),
    }


def validar(relatorio: dict[str, Any]) -> None:
    """Regras de evidência (spec, seção 6.1). Levanta ErroRelatorio com todos os problemas."""
    problemas = []
    consultas = set(relatorio["consultas"])
    for secao in ("achados", "inconclusivos", "descartados"):
        for bruto in relatorio[secao]:
            registro = RegistroAchado.model_validate(bruto)
            if not registro.achado.fatos:
                problemas.append(f"{registro.id}: achado sem evidência")
            faltando = sorted(_consultas_do_registro(registro) - consultas)
            if faltando:
                problemas.append(f"{registro.id}: cita consultas inexistentes {faltando}")
            for fonte in registro.achado.fontes_web:
                if not fonte.url or not fonte.acessado_em:
                    problemas.append(f"{registro.id}: fonte da web sem URL ou data de acesso")
            if secao == "achados" and (
                registro.situacao != "confirmado"
                or not registro.vereditos
                or registro.vereditos[-1].decisao != "confirmado"
            ):
                problemas.append(f"{registro.id}: entre os achados sem veredito confirmado")
    if relatorio["resumo"]:
        for destaque in relatorio["resumo"]["destaques"]:
            faltando = sorted(set(destaque["consultas"]) - consultas)
            if faltando:
                problemas.append(f"resumo: cita consultas inexistentes {faltando}")
    if problemas:
        raise ErroRelatorio("; ".join(problemas))


def _graficos_do_registro(registro: dict[str, Any], diario: Diario) -> list[dict[str, Any]]:
    renderizados = []
    for indice, bruto in enumerate(registro["achado"]["graficos"]):
        from agente.modelos import Grafico

        grafico = Grafico.model_validate(bruto)
        tabela = pq.read_table(diario.caminho_resultado(grafico.consulta))
        item: dict[str, Any] = {
            "id": f"g-{registro['id']}-{indice}",
            "tipo": grafico.tipo,
            "titulo": grafico.titulo,
            "consulta": grafico.consulta,
        }
        try:
            if grafico.tipo == "rede":
                item["svg"] = Markup(graficos.rede_svg(grafico, tabela))
            elif grafico.tipo in ("tabela", "cartoes"):
                item["colunas"] = tabela.column_names
                item["linhas"] = graficos.linhas(tabela, 50 if grafico.tipo == "tabela" else 1)
            else:
                item["spec"] = graficos.especificacao(grafico, tabela)
        except ValueError as erro:
            item["erro"] = str(erro)
        renderizados.append(item)
    return renderizados


def _finalizar(valor: Any) -> Any:
    """Toda saída de texto do template passa pela máscara de CPF (scripts embutidos não)."""
    if isinstance(valor, Markup) or not isinstance(valor, str):
        return valor
    return graficos.mascarar(valor)


def renderizar(relatorio: dict[str, Any], pasta: Path) -> str:
    diario = Diario(pasta)
    ambiente = Environment(
        loader=FileSystemLoader(PASTA_HTML), autoescape=True, finalize=_finalizar
    )
    secoes = ("achados", "inconclusivos", "descartados")
    visuais = {r["id"]: _graficos_do_registro(r, diario) for s in secoes for r in relatorio[s]}
    scripts = Markup(
        "\n".join(
            "<script>" + (PASTA_ESTATICOS / nome).read_text(encoding="utf-8") + "</script>"
            for nome in SCRIPTS
        )
    )
    return ambiente.get_template("relatorio.html.j2").render(
        rel=relatorio, visuais=visuais, scripts=scripts
    )


def gerar(estado: Estado, pasta: Path, gerado_em: datetime) -> Path:
    """Monta, valida e grava relatorio.json e relatorio.html; devolve o HTML."""
    relatorio = montar(estado, pasta, gerado_em)
    validar(relatorio)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "relatorio.json").write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
    )
    destino = pasta / "relatorio.html"
    destino.write_text(renderizar(relatorio, pasta), encoding="utf-8")
    return destino


def gerar_indice(investigacoes: Path) -> Path:
    """investigacoes/index.html: todas as investigações e o caderno de casos."""
    from agente import estado as persistencia
    from agente.caderno import Caderno

    itens = []
    for pasta in sorted(investigacoes.iterdir(), reverse=True) if investigacoes.exists() else []:
        if pasta.is_dir() and persistencia.existe(pasta):
            estado = persistencia.carregar(pasta)
            itens.append(
                {
                    "id": estado.id,
                    "tema": estado.tema,
                    "situacao": estado.situacao,
                    "criada_em": estado.criada_em.strftime("%d/%m/%Y %H:%M"),
                    "achados": sum(r.situacao == "confirmado" for r in estado.achados),
                    "tem_relatorio": (pasta / "relatorio.html").exists(),
                }
            )
    casos = Caderno(investigacoes / "caderno").listar()
    ambiente = Environment(
        loader=FileSystemLoader(PASTA_HTML), autoescape=True, finalize=_finalizar
    )
    html = ambiente.get_template("indice.html.j2").render(itens=itens, casos=casos)
    destino = investigacoes / "index.html"
    investigacoes.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding="utf-8")
    return destino
