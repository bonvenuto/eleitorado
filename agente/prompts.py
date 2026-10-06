"""Prompts de cada fase. As instruções permanentes ficam em .claude/agents/*.md; aqui vai a
tarefa da sessão com o contexto de que ela precisa (dados, aprendizados, hipótese, pendências)."""

from __future__ import annotations

from agente.caderno import Caso
from agente.modelos import Estado, Hipotese, RegistroAchado


def _contexto(contexto: str, aprendizados: str) -> str:
    partes = ["<contexto_dos_dados>", contexto.strip(), "</contexto_dos_dados>"]
    if aprendizados.strip():
        partes += ["<aprendizados>", aprendizados.strip(), "</aprendizados>"]
    return "\n".join(partes)


def explorar(
    estado: Estado,
    contexto: str,
    aprendizados: str,
    maximo: int,
    ultima_investigacao: str | None,
    pendentes: list[Hipotese],
) -> str:
    foco = (
        f"TEMA desta investigação: {estado.tema}\nTodas as hipóteses devem servir a esse tema."
        if estado.tema
        else "Investigação LIVRE: escolha o que olhar seguindo as lentes das suas instruções."
    )
    desde = (
        f"A investigação anterior foi em {ultima_investigacao}: priorize o que é novo desde então."
        if ultima_investigacao
        else "É a primeira investigação: não há caderno de casos anterior."
    )
    ja_na_fila = "\n".join(f"- {h.id}: {h.texto}" for h in pendentes) or "- (nenhuma)"
    return f"""FASE: EXPLORAR (investigação {estado.id})

{foco}
{desde}

Hipóteses que já estão na fila (vindas do caderno de casos; não repita):
{ja_na_fila}

Sua tarefa nesta sessão:
1. Faça um panorama com poucas consultas amplas (alertas do pipeline, concentração, saltos no tempo,
   valores fora da curva) para achar onde vale aprofundar.
2. Consulte o caderno (caderno_buscar) antes de propor algo sobre uma entidade: não reproponha
   casos descartados, a não ser que os dados tenham mudado.
3. Registre de 1 a {maximo} hipóteses com hipoteses_registrar, da mais para a menos promissora,
   cada uma com entidades concretas (CNPJ, raiz, órgão, parlamentar_id...) quando houver.
4. Termine a sessão logo depois de registrar. Não investigue a fundo agora.

{_contexto(contexto, aprendizados)}
"""


def investigar(
    estado: Estado,
    hipotese: Hipotese,
    contexto: str,
    aprendizados: str,
    casos: list[Caso],
    pendencias: list[str],
) -> str:
    historico = (
        "\n".join(
            f"- [{c.caso_id}] {c.situacao}: {c.titulo}"
            + (f" — {c.historico[-1].resumo}" if c.historico else "")
            for c in casos
        )
        or "- (nenhum caso ligado)"
    )
    rodada = (
        "O validador independente considerou o achado INCONCLUSIVO e pediu:\n"
        + "\n".join(f"- {p}" for p in pendencias)
        + "\nResponda a esses pontos com novas consultas e registre o achado revisado."
        if pendencias
        else "Primeira rodada desta hipótese."
    )
    entidades = ", ".join(f"{k}: {', '.join(v)}" for k, v in hipotese.entidades.items()) or "—"
    return f"""FASE: INVESTIGAR (investigação {estado.id}, hipótese {hipotese.id})

Hipótese {hipotese.id} (lente: {hipotese.lente}; prioridade {hipotese.prioridade}):
{hipotese.texto}
Entidades: {entidades}

{rodada}

Casos do caderno ligados a estas entidades:
{historico}

Sua tarefa nesta sessão:
1. Reúna evidências com consultas (cada número que você citar precisa vir de uma consulta qN).
2. Pense nas explicações inocentes e nos erros de dado antes de concluir
   (o validador vai testá-las).
3. Use a web só para validar (cadastros oficiais, notícias, diários oficiais); nunca pesquise CPF.
4. Termine com UMA das duas ações:
   - achado_registrar (hipotese_id = "{hipotese.id}"), com fatos, indícios, hipóteses, gráficos
     e recomendações; ou
   - hipotese_descartar, com o motivo, se os dados não sustentam a hipótese.
5. Se descobrir uma peculiaridade dos dados que evitaria erros futuros, use caderno_aprender.

{_contexto(contexto, aprendizados)}
"""


def validar(estado: Estado, registro: RegistroAchado, contexto: str, aprendizados: str) -> str:
    achado = registro.achado.model_dump_json(indent=1)
    anteriores = "\n".join(
        f"- rodada {i + 1}: {v.decisao} — {v.justificativa}"
        for i, v in enumerate(registro.vereditos)
    )
    return f"""FASE: VALIDAR (investigação {estado.id}, achado {registro.id})

Você é o validador independente. Tente DERRUBAR o achado abaixo. Não confie no texto: refaça as
consultas que importam e teste as explicações alternativas (homônimo, CNPJ de outra empresa,
sanção fora da vigência ou de abrangência restrita, erro ou duplicidade na fonte, carga histórica
incompleta, valor dentro do normal para o órgão ou o período).

Vereditos anteriores deste achado:
{anteriores or "- (primeira validação)"}

<achado>
{achado}
</achado>

Termine registrando o veredito com veredito_registrar:
- "confirmado": os fatos se sustentam e nenhuma alternativa explica o padrão (liste as
  alternativas testadas e o resultado de cada uma);
- "descartado": uma alternativa explica o padrão ou os fatos não se sustentam;
- "inconclusivo": faltam dados; diga exatamente o que falta checar (pendências).
Marque corroboracao_independente só se uma fonte oficial na web confirmar o achado, e cite-a.

{_contexto(contexto, aprendizados)}
"""


def correlacionar(estado: Estado, registro: RegistroAchado, contexto: str) -> str:
    achado = registro.achado.model_dump_json(indent=1)
    return f"""FASE: CORRELACIONAR (investigação {estado.id}, achado {registro.id})

O achado abaixo foi CONFIRMADO pelo validador. Procure casos relacionados nos dados:
- a mesma empresa por outra filial (mesma raiz de CNPJ) e outros órgãos que pagaram a ela;
- o mesmo órgão, parlamentar ou autor de emenda em situações parecidas;
- o mesmo padrão com outras entidades.

Registre os relacionados com correlacionados_registrar (cada um com as consultas que o mostram) e
termine. Se não houver, registre uma lista vazia.

<achado>
{achado}
</achado>

{_contexto(contexto, "")}
"""


def relatar(estado: Estado) -> str:
    linhas = []
    for registro in estado.achados:
        linhas.append(f"- {registro.id} ({registro.situacao}): {registro.achado.titulo}")
    for hipotese in estado.hipoteses:
        if hipotese.situacao == "descartada":
            linhas.append(f"- {hipotese.id} descartada: {hipotese.motivo}")
    resultados = "\n".join(linhas) or "- nenhum achado nem descarte"
    fatos = "\n".join(
        f"- {', '.join(fato.consultas)}: {fato.texto}"
        for registro in estado.achados
        if registro.situacao == "confirmado"
        for fato in registro.achado.fatos
    )
    return f"""FASE: RELATAR (investigação {estado.id})

Sua PRIMEIRA e única ação: chamar resumo_registrar. Não há consulta nova nesta fase (a ferramenta
recusa): use só os fatos abaixo, que já têm as consultas.

O resumo: 3 a 6 frases para quem vai decidir o que fazer, sem números no texto. Os números vão em
destaques (até 4), cada um copiando o valor de um fato abaixo e citando as mesmas consultas. Diga
também o que a investigação não conseguiu cobrir.

Resultados:
{resultados}

Fatos confirmados (consultas: texto):
{fatos or "- nenhum"}
"""
