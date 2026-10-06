"""Modelos do agente: hipóteses, achados, vereditos e o estado de uma investigação.

São também os parâmetros das ferramentas MCP: o esquema que o agente vê é o destes modelos.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ID_CONSULTA = r"^q[0-9]+$"
TipoAchado = Literal["insight estratégico", "situação suspeita", "qualidade de dado"]
Entidades = dict[str, list[str]]


class _Modelo(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NovaHipotese(_Modelo):
    """Hipótese proposta pelo agente na exploração."""

    texto: str = Field(min_length=10, description="O que se suspeita ou se quer entender")
    lente: str = Field(description="Lente de investigação (concentração, fracionamento...)")
    prioridade: int = Field(ge=1, le=5, description="1 = mais alta")
    entidades: Entidades = Field(
        default_factory=dict, description="Ex.: {'cnpj_raiz': ['12345678'], 'orgao': ['...']}"
    )


class Hipotese(NovaHipotese):
    """Hipótese na fila; `id`, `situacao` e `rodadas` são do controlador."""

    id: str = ""
    situacao: Literal["pendente", "candidata", "confirmada", "descartada", "inconclusiva"] = (
        "pendente"
    )
    rodadas: int = 0
    motivo: str | None = None
    origem: Literal["exploracao", "caderno", "tema"] = "exploracao"
    caso_id: str | None = None


class Afirmacao(_Modelo):
    texto: str = Field(min_length=3, description="Afirmação com os números que a sustentam")
    consultas: list[str] = Field(
        min_length=1, description="Ids das consultas (q1, q2...) de onde saem os números"
    )

    @model_validator(mode="after")
    def _ids(self) -> Afirmacao:
        invalidos = [c for c in self.consultas if not re.match(ID_CONSULTA, c)]
        if invalidos:
            raise ValueError(f"ids de consulta inválidos: {invalidos}")
        return self


class FonteWeb(_Modelo):
    url: str = Field(pattern=r"^https?://", description="Endereço consultado")
    titulo: str
    acessado_em: date
    trecho: str = Field(min_length=1, description="Trecho que sustenta a afirmação")


class Grafico(_Modelo):
    tipo: Literal["barras", "linha", "dispersao", "distribuicao", "rede", "cartoes", "tabela"]
    titulo: str
    consulta: str = Field(pattern=ID_CONSULTA, description="Consulta com os dados do gráfico")
    x: str | None = Field(default=None, description="Coluna do eixo x (categoria ou data)")
    y: str | None = Field(default=None, description="Coluna do valor")
    cor: str | None = Field(default=None, description="Coluna que separa séries")
    destaque: str | None = Field(default=None, description="Valor de x a destacar")
    origem: str | None = Field(default=None, description="Rede: coluna do nó de origem")
    destino: str | None = Field(default=None, description="Rede: coluna do nó de destino")
    peso: str | None = Field(default=None, description="Rede: coluna do peso da ligação")

    @model_validator(mode="after")
    def _campos(self) -> Grafico:
        exigidos = {
            "barras": ("x", "y"),
            "linha": ("x", "y"),
            "dispersao": ("x", "y"),
            "distribuicao": ("x",),
            "rede": ("origem", "destino"),
        }.get(self.tipo, ())
        faltando = [campo for campo in exigidos if not getattr(self, campo)]
        if faltando:
            raise ValueError(f"gráfico {self.tipo} exige {', '.join(faltando)}")
        return self


class Achado(_Modelo):
    hipotese_id: str
    tipo: TipoAchado
    padrao: str = Field(
        pattern=r"^[a-z0-9_]+$", description="Padrão em snake_case (ex.: fornecedor_sancionado)"
    )
    titulo: str = Field(min_length=5)
    entidades: Entidades = Field(min_length=1)
    fatos: list[Afirmacao] = Field(min_length=1, description="O que os dados mostram")
    indicios: list[str] = Field(default_factory=list, description="O que isso pode indicar")
    hipoteses: list[str] = Field(default_factory=list, description="O que não se sabe")
    fontes_web: list[FonteWeb] = Field(default_factory=list)
    graficos: list[Grafico] = Field(default_factory=list)
    recomendacoes: list[str] = Field(
        default_factory=list, description="O que o usuário pode fazer (o agente não age)"
    )

    @model_validator(mode="after")
    def _numeros_so_nos_fatos(self) -> Achado:
        """Todo número do relatório aponta para uma consulta: valores ficam nos fatos."""
        textos = [self.titulo, *self.indicios, *self.hipoteses, *self.recomendacoes]
        com_numero = [t for t in textos if tem_valor(t)]
        if com_numero:
            raise ValueError(
                "valores (R$, %, números com 3+ dígitos) só nos fatos, com a consulta: "
                + "; ".join(t[:60] for t in com_numero)
            )
        return self

    def consultas_citadas(self) -> set[str]:
        citadas = {c for fato in self.fatos for c in fato.consultas}
        return citadas | {grafico.consulta for grafico in self.graficos}


def tem_valor(texto: str) -> bool:
    """Valor que precisa de fonte: R$, porcentagem ou número com 3+ dígitos (anos e números de
    lei não contam)."""
    sem_leis = re.sub(r"\blei\s+(n[º°o.]?\s*)?[\d.]+(/\d+)?", "", texto, flags=re.IGNORECASE)
    sem_anos = re.sub(r"\b(19|20)\d{2}\b", "", sem_leis)
    return bool(re.search(r"R\$|%|\d[\d.,]*\d{2}|\d+[.,]\d", sem_anos))


class Alternativa(_Modelo):
    explicacao: str = Field(description="Explicação inocente ou erro de dado testado")
    resultado: str = Field(description="Por que se sustenta ou não")
    consultas: list[str] = Field(default_factory=list)


class Veredito(_Modelo):
    decisao: Literal["confirmado", "descartado", "inconclusivo"]
    justificativa: str = Field(min_length=10)
    alternativas: list[Alternativa] = Field(default_factory=list)
    pendencias: list[str] = Field(
        default_factory=list, description="Inconclusivo: o que falta checar"
    )
    corroboracao_independente: bool = Field(
        default=False, description="Fonte oficial na web confirma o achado"
    )
    fontes_web: list[FonteWeb] = Field(default_factory=list)

    @model_validator(mode="after")
    def _coerente(self) -> Veredito:
        if self.decisao == "inconclusivo" and not self.pendencias:
            raise ValueError("veredito inconclusivo exige pendências")
        if self.corroboracao_independente and not self.fontes_web:
            raise ValueError("corroboração independente exige fonte da web")
        if self.decisao == "confirmado" and not self.alternativas:
            raise ValueError("confirmar exige ao menos uma explicação alternativa testada")
        return self


class Correlacionado(_Modelo):
    descricao: str
    entidades: Entidades = Field(min_length=1)
    consultas: list[str] = Field(min_length=1)


class Resumo(_Modelo):
    texto: str = Field(min_length=20, description="Resumo executivo da investigação")
    destaques: list[Afirmacao] = Field(
        default_factory=list, description="Números-chave (viram cartões)"
    )


class RegistroAchado(_Modelo):
    id: str
    achado: Achado
    vereditos: list[Veredito] = Field(default_factory=list)
    situacao: Literal["em_validacao", "confirmado", "descartado", "inconclusivo"] = "em_validacao"
    confianca: Literal["alta", "média"] | None = None
    correlacionados: list[Correlacionado] = Field(default_factory=list)


class Uso(_Modelo):
    ciclos: int = 0
    consultas: int = 0
    segundos: float = 0
    sessoes: int = 0


Fase = Literal[
    "preparar", "explorar", "investigar", "correlacionar", "relatar", "encerrar", "concluida"
]


class Transicao(_Modelo):
    fase: Fase
    em: datetime
    motivo: str = ""


class Estado(_Modelo):
    id: str
    tema: str | None = None
    criada_em: datetime
    fase: Fase = "preparar"
    situacao: Literal["em_andamento", "pausada", "concluida", "parcial"] = "em_andamento"
    versao_dados: dict[str, str] = Field(default_factory=dict)
    hipoteses: list[Hipotese] = Field(default_factory=list)
    achados: list[RegistroAchado] = Field(default_factory=list)
    resumo: Resumo | None = None
    uso: Uso = Field(default_factory=Uso)
    motivo_parada: str | None = None
    transicoes: list[Transicao] = Field(default_factory=list)

    def hipotese(self, hipotese_id: str) -> Hipotese:
        for hipotese in self.hipoteses:
            if hipotese.id == hipotese_id:
                return hipotese
        raise KeyError(hipotese_id)

    def achado(self, achado_id: str) -> RegistroAchado:
        for registro in self.achados:
            if registro.id == achado_id:
                return registro
        raise KeyError(achado_id)
