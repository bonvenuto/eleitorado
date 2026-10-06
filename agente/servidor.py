"""Servidor MCP com as ferramentas do agente.

O controlador inicia uma sessão do Claude por fase e passa, nas variáveis de ambiente, a pasta da
investigação, o papel (investigador ou validador), a fase e o alvo (hipótese ou achado). O servidor
só expõe as ferramentas do papel e recusa escritas fora da fase ou do alvo. As ferramentas não têm
efeito fora de investigacoes/<id>/ e do caderno: o agente não age, só investiga e registra.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import duckdb
from mcp.server.mcpserver.exceptions import ToolError

from agente import estado as persistencia
from agente.caderno import Caderno
from agente.config import ConfigAgente, carregar
from agente.consulta import ErroConsulta, abrir, executar
from agente.diario import Diario
from agente.modelos import (
    Achado,
    Correlacionado,
    Hipotese,
    NovaHipotese,
    RegistroAchado,
    Resumo,
    Veredito,
)

FERRAMENTAS_POR_PAPEL = {
    "investigador": [
        "consultar",
        "caderno_buscar",
        "caderno_aprender",
        "hipoteses_registrar",
        "hipotese_descartar",
        "achado_registrar",
        "correlacionados_registrar",
        "resumo_registrar",
    ],
    "validador": ["consultar", "caderno_buscar", "veredito_registrar"],
}


class ErroFerramenta(ToolError):
    """Uso indevido de uma ferramenta; a mensagem volta para o agente corrigir (só a mensagem de
    um ToolError chega ao cliente MCP; outras exceções viram um erro genérico)."""


@dataclass(frozen=True)
class Sessao:
    pasta: Path  # investigacoes/<id>
    papel: str  # investigador ou validador
    fase: str  # explorar, investigar, validar, correlacionar ou relatar
    alvo: str | None  # hipótese (investigar) ou achado (validar, correlacionar)
    config: ConfigAgente

    @classmethod
    def do_ambiente(cls, env: Mapping[str, str], config: ConfigAgente) -> Sessao:
        return cls(
            pasta=Path(env["AGENTE_INVESTIGACAO"]),
            papel=env["AGENTE_PAPEL"],
            fase=env["AGENTE_FASE"],
            alvo=env.get("AGENTE_ALVO") or None,
            config=config,
        )


class Ferramentas:
    def __init__(
        self,
        sessao: Sessao,
        abrir_conexao: Callable[[], duckdb.DuckDBPyConnection] | None = None,
        hoje: Callable[[], date] = date.today,
    ) -> None:
        self.sessao = sessao
        self.diario = Diario(sessao.pasta)
        self.caderno = Caderno(sessao.config.caderno)
        self._abrir = abrir_conexao or (
            lambda: abrir(sessao.config.banco, sessao.config.diretorios_permitidos())
        )
        self._conexao: duckdb.DuckDBPyConnection | None = None
        self._hoje = hoje

    # ---------------------------------------------------------------- auxiliares

    def _exigir(self, fase: str) -> None:
        if self.sessao.fase != fase:
            raise ErroFerramenta(
                f"esta ferramenta é da fase {fase}; a sessão é de {self.sessao.fase}"
            )

    def _consultas_existentes(self, citadas: set[str]) -> None:
        faltando = sorted(citadas - set(self.diario.consultas()))
        if faltando:
            raise ErroFerramenta(f"consultas citadas que não existem no diário: {faltando}")

    # ---------------------------------------------------------------- leitura

    def consultar(self, sql: str) -> str:
        """Executa UMA instrução SELECT (ou WITH) no banco só de leitura e devolve as linhas.

        Tabelas: schemas `staging`, `intermediate` e `marts` (veja o contexto). Cada consulta
        recebe um id (q1, q2...) que deve ser citado nos fatos e gráficos.
        """
        if self._conexao is None:
            self._conexao = self._abrir()
        config = self.sessao.config
        try:
            resultado = executar(
                self._conexao,
                sql,
                self.diario,
                self.sessao.papel,
                tempo_maximo_s=config.tempo_consulta_s,
                linhas_exibidas=config.linhas_exibidas,
                linhas_salvas=config.linhas_salvas,
            )
        except ErroConsulta as erro:
            raise ErroFerramenta(str(erro)) from None
        return resultado.texto

    def caderno_buscar(self, termo: str) -> str:
        """Busca no caderno de casos (investigações anteriores) por CNPJ, raiz, nome ou órgão."""
        casos = self.caderno.buscar(termo)
        if not casos:
            return f"nenhum caso com '{termo}'"
        linhas = []
        for caso in casos:
            ultimo = caso.historico[-1] if caso.historico else None
            detalhe = f" — {ultimo.data}: {ultimo.resumo}" if ultimo else ""
            linhas.append(f"[{caso.caso_id}] {caso.situacao}: {caso.titulo}{detalhe}")
        return "\n".join(linhas)

    # ---------------------------------------------------------------- escrita (investigador)

    def caderno_aprender(self, texto: str) -> str:
        """Propõe um aprendizado sobre os dados (peculiaridade que evita erro em outra vez)."""
        if len(texto.strip()) < 10:
            raise ErroFerramenta("aprendizado muito curto")
        self.caderno.aprender(texto, self.sessao.pasta.name, self._hoje())
        return "aprendizado registrado"

    def hipoteses_registrar(self, hipoteses: list[NovaHipotese]) -> str:
        """Registra as hipóteses a investigar (fase de exploração), em ordem de prioridade."""
        self._exigir("explorar")
        if not hipoteses:
            raise ErroFerramenta("envie ao menos uma hipótese")
        estado = persistencia.carregar(self.sessao.pasta)
        origem = "tema" if estado.tema else "exploracao"
        novas = []
        for nova in hipoteses:
            identificador = f"h{len(estado.hipoteses) + 1}"
            estado.hipoteses.append(Hipotese(**nova.model_dump(), id=identificador, origem=origem))
            novas.append(identificador)
        persistencia.salvar(self.sessao.pasta, estado)
        return f"hipóteses registradas: {', '.join(novas)}"

    def hipotese_descartar(self, motivo: str) -> str:
        """Descarta a hipótese desta sessão, com o motivo (o que os dados mostraram)."""
        self._exigir("investigar")
        estado = persistencia.carregar(self.sessao.pasta)
        hipotese = estado.hipotese(self.sessao.alvo or "")
        hipotese.situacao = "descartada"
        hipotese.motivo = motivo
        persistencia.salvar(self.sessao.pasta, estado)
        return f"hipótese {hipotese.id} descartada"

    def achado_registrar(self, achado: Achado) -> str:
        """Registra o achado da hipótese desta sessão; ele vai para o validador independente."""
        self._exigir("investigar")
        if achado.hipotese_id != self.sessao.alvo:
            raise ErroFerramenta(f"a hipótese desta sessão é {self.sessao.alvo}")
        self._consultas_existentes(achado.consultas_citadas())
        estado = persistencia.carregar(self.sessao.pasta)
        hipotese = estado.hipotese(achado.hipotese_id)
        existente = next(
            (r for r in estado.achados if r.achado.hipotese_id == achado.hipotese_id), None
        )
        if existente is None:
            registro = RegistroAchado(id=f"a{len(estado.achados) + 1}", achado=achado)
            estado.achados.append(registro)
        else:  # nova rodada depois de um veredito inconclusivo
            existente.achado = achado
            existente.situacao = "em_validacao"
            registro = existente
        hipotese.situacao = "candidata"
        persistencia.salvar(self.sessao.pasta, estado)
        return f"achado {registro.id} registrado; segue para validação"

    def correlacionados_registrar(self, correlacionados: list[Correlacionado]) -> str:
        """Registra os casos relacionados ao achado confirmado desta sessão."""
        self._exigir("correlacionar")
        self._consultas_existentes({c for item in correlacionados for c in item.consultas})
        estado = persistencia.carregar(self.sessao.pasta)
        registro = estado.achado(self.sessao.alvo or "")
        registro.correlacionados = list(correlacionados)
        persistencia.salvar(self.sessao.pasta, estado)
        return f"{len(correlacionados)} correlacionado(s) registrado(s) em {registro.id}"

    def resumo_registrar(self, resumo: Resumo) -> str:
        """Registra o resumo executivo do relatório."""
        self._exigir("relatar")
        self._consultas_existentes({c for d in resumo.destaques for c in d.consultas})
        estado = persistencia.carregar(self.sessao.pasta)
        estado.resumo = resumo
        persistencia.salvar(self.sessao.pasta, estado)
        return "resumo registrado"

    # ---------------------------------------------------------------- escrita (validador)

    def veredito_registrar(self, veredito: Veredito) -> str:
        """Registra o veredito sobre o achado da sessão: confirmado, descartado ou inconclusivo."""
        self._exigir("validar")
        self._consultas_existentes({c for a in veredito.alternativas for c in a.consultas})
        estado = persistencia.carregar(self.sessao.pasta)
        registro = estado.achado(self.sessao.alvo or "")
        registro.vereditos.append(veredito)
        persistencia.salvar(self.sessao.pasta, estado)
        return f"veredito registrado para {registro.id}"


def criar_servidor(ferramentas: Ferramentas):
    from mcp.server import MCPServer

    servidor = MCPServer("agente")
    for nome in FERRAMENTAS_POR_PAPEL[ferramentas.sessao.papel]:
        servidor.add_tool(getattr(ferramentas, nome), name=nome)
    return servidor


def main() -> None:
    arquivo = os.environ.get("AGENTE_CONFIG")  # a avaliação usa um config.toml próprio
    config = carregar(Path(arquivo)) if arquivo else carregar()
    os.chdir(config.raiz)  # as views do banco usam caminhos relativos à raiz do repositório
    sessao = Sessao.do_ambiente(os.environ, config)
    criar_servidor(Ferramentas(sessao)).run()


if __name__ == "__main__":
    main()
