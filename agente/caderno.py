"""Caderno de casos: memória entre investigações (investigacoes/caderno/).

Um caso é um padrão sobre entidades (raiz de CNPJ, órgão, parlamentar...). O mesmo padrão sobre
as mesmas entidades é o mesmo caso, em qualquer investigação.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from pydantic import Field

from agente.modelos import Entidades, RegistroAchado, _Modelo

SituacaoCaso = Literal["aberto", "inconclusivo", "confirmado", "descartado"]
SITUACAO_DO_ACHADO: dict[str, SituacaoCaso] = {
    "confirmado": "confirmado",
    "descartado": "descartado",
    "inconclusivo": "inconclusivo",
    "em_validacao": "aberto",
}


class ConsultaChave(_Modelo):
    sql: str
    linhas: int
    soma: float | None = None  # soma das colunas numéricas: detecta mudança de valor


class EntradaHistorico(_Modelo):
    investigacao: str
    data: date
    veredito: str
    resumo: str
    relatorio: str  # caminho relativo a investigacoes/


class Caso(_Modelo):
    caso_id: str
    titulo: str
    tipo: str
    padrao: str
    entidades: Entidades
    situacao: SituacaoCaso
    confianca: str | None = None
    historico: list[EntradaHistorico] = Field(default_factory=list)
    consultas_chave: list[ConsultaChave] = Field(default_factory=list)
    atualizado_em: datetime


def caso_id(padrao: str, entidades: Entidades) -> str:
    """Hash estável do padrão e das entidades (ordem de chaves e valores não importa)."""
    partes = [padrao] + [
        f"{chave}={valor}"
        for chave in sorted(entidades)
        for valor in sorted(v.strip().upper() for v in entidades[chave])
    ]
    return hashlib.sha1("|".join(partes).encode("utf-8")).hexdigest()[:12]


def mudou(anterior: ConsultaChave, linhas: int, soma: float | None) -> bool:
    """Mudança relevante: outro número de linhas ou soma com variação acima de 10%."""
    if linhas != anterior.linhas:
        return True
    if anterior.soma is None or soma is None:
        return anterior.soma != soma
    if anterior.soma == 0:
        return soma != 0
    return abs(soma - anterior.soma) / abs(anterior.soma) > 0.10


class Caderno:
    def __init__(self, pasta: Path) -> None:
        self.pasta = pasta
        self._casos = pasta / "casos"
        self._aprendizados = pasta / "aprendizados.md"

    def obter(self, identificador: str) -> Caso | None:
        arquivo = self._casos / f"{identificador}.json"
        if not arquivo.exists():
            return None
        return Caso.model_validate_json(arquivo.read_text(encoding="utf-8"))

    def salvar(self, caso: Caso) -> None:
        self._casos.mkdir(parents=True, exist_ok=True)
        arquivo = self._casos / f"{caso.caso_id}.json"
        arquivo.write_text(caso.model_dump_json(indent=1), encoding="utf-8")

    def listar(self, situacao: SituacaoCaso | None = None) -> list[Caso]:
        if not self._casos.exists():
            return []
        casos = [
            Caso.model_validate_json(arquivo.read_text(encoding="utf-8"))
            for arquivo in sorted(self._casos.glob("*.json"))
        ]
        return [caso for caso in casos if situacao is None or caso.situacao == situacao]

    def buscar(self, termo: str) -> list[Caso]:
        """Casos cujo título ou entidade contém o termo; um CNPJ também acha a sua raiz."""
        alvo = termo.strip().upper()
        digitos = "".join(c for c in alvo if c.isalnum())
        alvos = {alvo, digitos} | ({digitos[:8]} if len(digitos) == 14 else set())
        alvos.discard("")
        encontrados = []
        for caso in self.listar():
            valores = [v.upper() for lista in caso.entidades.values() for v in lista]
            if any(a in caso.titulo.upper() or any(a in v for v in valores) for a in alvos):
                encontrados.append(caso)
        return encontrados

    def registrar(
        self,
        registro: RegistroAchado,
        investigacao: str,
        dia: date,
        relatorio: str,
        consultas_chave: list[ConsultaChave],
        agora: datetime,
    ) -> Caso:
        """Cria ou atualiza o caso do achado com o resultado desta investigação."""
        achado = registro.achado
        identificador = caso_id(achado.padrao, achado.entidades)
        caso = self.obter(identificador) or Caso(
            caso_id=identificador,
            titulo=achado.titulo,
            tipo=achado.tipo,
            padrao=achado.padrao,
            entidades=achado.entidades,
            situacao="aberto",
            atualizado_em=agora,
        )
        resumo = registro.vereditos[-1].justificativa if registro.vereditos else achado.titulo
        caso = caso.model_copy(
            update={
                "titulo": achado.titulo,
                "situacao": SITUACAO_DO_ACHADO[registro.situacao],
                "confianca": registro.confianca,
                "consultas_chave": consultas_chave or caso.consultas_chave,
                "atualizado_em": agora,
                "historico": [
                    *caso.historico,
                    EntradaHistorico(
                        investigacao=investigacao,
                        data=dia,
                        veredito=registro.situacao,
                        resumo=resumo,
                        relatorio=relatorio,
                    ),
                ],
            }
        )
        self.salvar(caso)
        return caso

    def aprendizados(self) -> str:
        if not self._aprendizados.exists():
            return ""
        return self._aprendizados.read_text(encoding="utf-8")

    def aprender(self, texto: str, investigacao: str, dia: date) -> None:
        self.pasta.mkdir(parents=True, exist_ok=True)
        novo = not self._aprendizados.exists()
        with self._aprendizados.open("a", encoding="utf-8") as saida:
            if novo:
                saida.write(
                    "# Aprendizados sobre os dados\n\n"
                    "Notas propostas pelo agente; revise e edite à vontade.\n\n"
                )
            linha = " ".join(texto.split())
            saida.write(f"- {linha} _(investigação {investigacao}, {dia.isoformat()})_\n")
