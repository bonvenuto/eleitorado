"""Controlador: o laço externo de uma investigação (máquina de estados persistida).

PREPARAR → EXPLORAR → INVESTIGAR ⇄ VALIDAR → CORRELACIONAR → RELATAR → ENCERRAR

Cada fase com o Claude é uma sessão nova (contexto limpo). Entre sessões, o estado é do
controlador: ele aplica os orçamentos, decide a situação de cada achado a partir do veredito do
validador (o investigador não confirma nada) e salva tudo, para retomar de onde parou.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pyarrow.parquet as pq

from agente import estado as persistencia
from agente import prompts
from agente.caderno import Caderno, ConsultaChave
from agente.config import ConfigAgente, Orcamento, preparo_c2_pendente
from agente.diario import Diario
from agente.executor import Executor, Limites, PedidoSessao, ResultadoSessao
from agente.modelos import Estado, Hipotese, Resumo, Transicao
from agente.preparar import ErroPreparo, Preparo, _somar
from agente.relatorio import ErroRelatorio, confianca, gerar, gerar_indice

CICLOS_POR_SESSAO = 25
CICLOS_EXPLORAR = 40  # a exploração faz um panorama antes de registrar as hipóteses
CICLOS_REGISTRO = 12  # sessão curta quando a exploração termina sem registrar
RESERVA_HIPOTESE = 20  # ciclos para investigar, validar e correlacionar uma hipótese nova
MINIMO_VALIDACAO = 12  # a validação de um achado registrado não fica sem ciclos
CICLOS_RELATAR = 10  # o resumo executivo é escrito mesmo com o orçamento esgotado
MINUTOS_POR_SESSAO = 20
TRAVA_ORFA = timedelta(hours=6)
ERROS_SEGUIDOS_PARA_PAUSAR = 2


def resumo_automatico(estado: Estado) -> Resumo:
    """Resumo montado pelo controlador quando o agente não registrou o seu."""
    contagem = {
        situacao: [r for r in estado.achados if r.situacao == situacao]
        for situacao in ("confirmado", "inconclusivo", "descartado")
    }
    partes = [
        "Resumo automático (o agente não registrou o resumo executivo).",
        f"Achados confirmados: {len(contagem['confirmado'])}; inconclusivos: "
        f"{len(contagem['inconclusivo'])}; descartados: {len(contagem['descartado'])}.",
    ]
    partes += [f"Confirmado: {r.achado.titulo}." for r in contagem["confirmado"]]
    partes += [f"Inconclusivo: {r.achado.titulo}." for r in contagem["inconclusivo"]]
    return Resumo(texto=" ".join(partes))


class ErroTrava(Exception):
    """Outra investigação está em andamento."""


@dataclass
class Dependencias:
    config: ConfigAgente
    executor: Executor
    preparar: Callable[[], Preparo]
    agora: Callable[[], datetime] = lambda: datetime.now(UTC)


def identificador(agora: datetime, tema: str | None) -> str:
    base = unicodedata.normalize("NFKD", tema or "livre").encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")[:40] or "livre"
    return f"{agora:%Y%m%d-%H%M}-{slug}"


@contextmanager
def trava(investigacoes: Path, agora: datetime):
    """Uma investigação por vez; trava com mais de 6 horas é órfã (processo que morreu)."""
    arquivo = investigacoes / ".trava"
    investigacoes.mkdir(parents=True, exist_ok=True)
    if arquivo.exists():
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        desde = datetime.fromisoformat(dados["desde"])
        if agora - desde < TRAVA_ORFA:
            raise ErroTrava(
                f"investigação em andamento desde {dados['desde']} (pid {dados['pid']})"
            )
    arquivo.write_text(json.dumps({"pid": os.getpid(), "desde": agora.isoformat()}), "utf-8")
    try:
        yield
    finally:
        arquivo.unlink(missing_ok=True)


class Controlador:
    def __init__(self, deps: Dependencias) -> None:
        self.deps = deps
        self.config = deps.config
        self.caderno = Caderno(deps.config.caderno)
        self._erros_seguidos = 0

    # ---------------------------------------------------------------- ciclo de vida

    def nova(self, tema: str | None) -> Path:
        agora = self.deps.agora()
        pasta = self.config.investigacoes / identificador(agora, tema)
        persistencia.salvar(pasta, Estado(id=pasta.name, tema=tema, criada_em=agora))
        return pasta

    def descartar_se_nao_comecou(self, pasta: Path) -> bool:
        """Apaga a investigação que falhou antes de sair da preparação (não tem nada a retomar)."""
        import shutil

        estado = persistencia.carregar(pasta)
        if estado.fase != "preparar" or estado.hipoteses or estado.achados:
            return False
        shutil.rmtree(pasta)
        return True

    def pendente(self) -> Path | None:
        """A investigação mais recente que ficou pausada ou em andamento."""
        if not self.config.investigacoes.exists():
            return None
        for pasta in sorted(self.config.investigacoes.iterdir(), reverse=True):
            if pasta.is_dir() and persistencia.existe(pasta):
                if persistencia.carregar(pasta).situacao in ("pausada", "em_andamento"):
                    return pasta
        return None

    def executar(self, pasta: Path) -> Estado:
        estado = persistencia.carregar(pasta)
        if estado.situacao == "pausada":
            estado.situacao = "em_andamento"
            estado.motivo_parada = None
            persistencia.salvar(pasta, estado)
        while estado.fase != "concluida" and estado.situacao != "pausada":
            etapa = getattr(self, f"_fase_{estado.fase}")
            etapa(pasta)
            estado = persistencia.carregar(pasta)
        return estado

    # ---------------------------------------------------------------- auxiliares

    def _orcamento(self, estado: Estado) -> Orcamento:
        return self.config.orcamento(estado.tema)

    def _esgotado(self, estado: Estado) -> str | None:
        orcamento = self._orcamento(estado)
        if estado.uso.ciclos >= orcamento.ciclos:
            return f"orçamento de ciclos esgotado ({estado.uso.ciclos}/{orcamento.ciclos})"
        if estado.uso.segundos >= orcamento.minutos * 60:
            return f"orçamento de tempo esgotado ({estado.uso.segundos / 60:.0f} min)"
        return None

    def _transicao(self, pasta: Path, fase: str, motivo: str = "") -> None:
        estado = persistencia.carregar(pasta)
        estado.fase = fase  # type: ignore[assignment]
        estado.transicoes.append(Transicao(fase=fase, em=self.deps.agora(), motivo=motivo))
        persistencia.salvar(pasta, estado)

    def _parar_por_orcamento(self, pasta: Path, motivo: str) -> None:
        estado = persistencia.carregar(pasta)
        estado.motivo_parada = motivo
        persistencia.salvar(pasta, estado)
        self._transicao(pasta, "relatar", motivo)

    def _contexto(self) -> tuple[str, str]:
        arquivo = self.config.investigacoes / "contexto.md"
        contexto = arquivo.read_text(encoding="utf-8") if arquivo.exists() else ""
        return contexto, self.caderno.aprendizados()

    def _sessao(
        self,
        pasta: Path,
        agente: str,
        fase: str,
        alvo: str | None,
        prompt: str,
        minimo: int = 1,
        maximo: int = CICLOS_POR_SESSAO,
    ) -> ResultadoSessao:
        """Uma sessão com o que resta do orçamento, entre `minimo` e `maximo` ciclos (o mínimo
        pode passar do orçamento: a validação de um achado registrado não fica sem ciclos)."""
        if preparo_c2_pendente(self.config.lago):
            raise ErroPreparo("preparo C2 pendente; sessão bloqueada até reconstrução")
        estado = persistencia.carregar(pasta)
        orcamento = self._orcamento(estado)
        limites = Limites(
            ciclos=max(minimo, min(maximo, orcamento.ciclos - estado.uso.ciclos)),
            segundos=max(
                60, min(MINUTOS_POR_SESSAO * 60, orcamento.minutos * 60 - estado.uso.segundos)
            ),
        )
        resultado = self.deps.executor.rodar(
            PedidoSessao(agente=agente, fase=fase, alvo=alvo, prompt=prompt, pasta=pasta), limites
        )
        estado = persistencia.carregar(pasta)  # o servidor MCP registrou durante a sessão
        estado.uso.ciclos += resultado.ciclos
        estado.uso.segundos += resultado.segundos
        estado.uso.sessoes += 1
        estado.uso.consultas = len(Diario(pasta).consultas())
        self._erros_seguidos = self._erros_seguidos + 1 if resultado.parada == "erro" else 0
        if resultado.parada == "limite_uso" or self._erros_seguidos >= ERROS_SEGUIDOS_PARA_PAUSAR:
            estado.situacao = "pausada"
            estado.motivo_parada = f"{resultado.parada}: {resultado.detalhe}"
        persistencia.salvar(pasta, estado)
        return resultado

    # ---------------------------------------------------------------- fases

    def _fase_preparar(self, pasta: Path) -> None:
        preparo = self.deps.preparar()
        estado = persistencia.carregar(pasta)
        estado.versao_dados = preparo.versao_dados
        if not estado.tema:  # na investigação livre, o caderno entra na fila
            for caso in preparo.revisar:
                estado.hipoteses.append(
                    Hipotese(
                        id=f"h{len(estado.hipoteses) + 1}",
                        texto=f"Atualização do caso '{caso.titulo}': os dados mudaram desde "
                        f"o veredito '{caso.situacao}'",
                        lente="atualização do caderno",
                        prioridade=1,
                        entidades=caso.entidades,
                        origem="caderno",
                        caso_id=caso.caso_id,
                    )
                )
            for caso in self.caderno.listar("inconclusivo"):
                pendencia = caso.historico[-1].resumo if caso.historico else ""
                estado.hipoteses.append(
                    Hipotese(
                        id=f"h{len(estado.hipoteses) + 1}",
                        texto=f"Pendência do caso '{caso.titulo}': {pendencia}",
                        lente="pendência do caderno",
                        prioridade=2,
                        entidades=caso.entidades,
                        origem="caderno",
                        caso_id=caso.caso_id,
                    )
                )
        persistencia.salvar(pasta, estado)
        self._transicao(pasta, "explorar")

    def _ultima_investigacao(self, atual: str) -> str | None:
        datas = []
        for outra in self.config.investigacoes.iterdir():
            if outra.name != atual and persistencia.existe(outra):
                anterior = persistencia.carregar(outra)
                if anterior.situacao in ("concluida", "parcial"):
                    datas.append(anterior.criada_em)
        return max(datas).date().isoformat() if datas else None

    def _fase_explorar(self, pasta: Path) -> None:
        estado = persistencia.carregar(pasta)
        motivo = self._esgotado(estado)
        if motivo:
            self._parar_por_orcamento(pasta, motivo)
            return
        contexto, aprendizados = self._contexto()
        maximo = self._orcamento(estado).hipoteses
        pendentes = [h for h in estado.hipoteses if h.situacao == "pendente"]
        prompt = prompts.explorar(
            estado, contexto, aprendizados, maximo, self._ultima_investigacao(estado.id), pendentes
        )
        antes = len(estado.hipoteses)
        self._sessao(pasta, "investigador", "explorar", None, prompt, maximo=CICLOS_EXPLORAR)
        estado = persistencia.carregar(pasta)
        if estado.situacao == "pausada":
            return
        sem_fila = not any(h.situacao == "pendente" for h in estado.hipoteses)
        if len(estado.hipoteses) == antes and sem_fila and not self._esgotado(estado):
            consultas = list(Diario(pasta).consultas().values())
            prompt = prompts.registrar_hipoteses(estado, consultas, maximo)
            limite = CICLOS_REGISTRO
            self._sessao(pasta, "investigador", "explorar", None, prompt, limite, limite)
            if persistencia.carregar(pasta).situacao == "pausada":
                return
        self._transicao(pasta, "investigar")

    def _proxima(self, estado: Estado) -> Hipotese | None:
        """Próxima hipótese a investigar: até N por investigação, as do caderno primeiro."""
        maximo = self._orcamento(estado).hipoteses
        ordenadas = sorted(
            estado.hipoteses, key=lambda h: (h.origem != "caderno", h.prioridade, int(h.id[1:]))
        )
        escolhidas = ordenadas[:maximo]
        return next((h for h in escolhidas if h.situacao in ("pendente", "candidata")), None)

    def _fase_investigar(self, pasta: Path) -> None:
        while True:
            estado = persistencia.carregar(pasta)
            if estado.situacao == "pausada":
                return
            hipotese = self._proxima(estado)
            if hipotese is None:
                self._transicao(pasta, "relatar")
                return
            registro = self._registro_da_hipotese(estado, hipotese.id)
            aguardando_validacao = registro is not None and registro.situacao == "em_validacao"
            motivo = self._esgotado(estado)
            restante = self._orcamento(estado).ciclos - estado.uso.ciclos
            if not motivo and hipotese.situacao == "pendente" and restante < RESERVA_HIPOTESE:
                motivo = f"orçamento: {restante} ciclos não bastam para outra hipótese"
            if motivo and not aguardando_validacao:  # achado registrado sempre é validado
                self._parar_por_orcamento(pasta, motivo)
                return
            self._investigar_hipotese(pasta, hipotese.id)

    def _registro_da_hipotese(self, estado: Estado, hipotese_id: str):
        return next((r for r in estado.achados if r.achado.hipotese_id == hipotese_id), None)

    def _investigar_hipotese(self, pasta: Path, hipotese_id: str) -> None:
        """Sessão do investigador (primeira rodada ou revisão pedida pelo validador) e validação.

        Um achado em validação (registrado e ainda sem veredito) vai direto ao validador: é a
        retomada depois de uma interrupção entre o registro e a validação.
        """
        estado = persistencia.carregar(pasta)
        hipotese = estado.hipotese(hipotese_id)
        registro = self._registro_da_hipotese(estado, hipotese_id)
        if registro is None or registro.situacao != "em_validacao":
            pendencias = (
                registro.vereditos[-1].pendencias if registro and registro.vereditos else []
            )
            contexto, aprendizados = self._contexto()
            casos = [
                caso
                for valores in hipotese.entidades.values()
                for valor in valores
                for caso in self.caderno.buscar(valor)
            ]
            prompt = prompts.investigar(estado, hipotese, contexto, aprendizados, casos, pendencias)
            resultado = self._sessao(pasta, "investigador", "investigar", hipotese_id, prompt)
            estado = persistencia.carregar(pasta)
            if estado.situacao == "pausada":
                return
            hipotese = estado.hipotese(hipotese_id)
            registro = self._registro_da_hipotese(estado, hipotese_id)
            if hipotese.situacao == "descartada":
                if registro is not None:
                    registro.situacao = "descartado"
                    persistencia.salvar(pasta, estado)
                return
            if registro is None or registro.situacao != "em_validacao":
                hipotese.situacao = "inconclusiva"
                hipotese.motivo = f"a sessão terminou sem achado nem descarte ({resultado.parada})"
                persistencia.salvar(pasta, estado)
                return
        self._validar(pasta, registro.id)

    def _validar(self, pasta: Path, achado_id: str) -> None:
        estado = persistencia.carregar(pasta)
        registro = estado.achado(achado_id)
        antes = len(registro.vereditos)
        contexto, aprendizados = self._contexto()
        prompt = prompts.validar(estado, registro, contexto, aprendizados)
        self._sessao(pasta, "validador", "validar", achado_id, prompt, minimo=MINIMO_VALIDACAO)
        estado = persistencia.carregar(pasta)
        if estado.situacao == "pausada":
            return
        registro = estado.achado(achado_id)
        hipotese = estado.hipotese(registro.achado.hipotese_id)
        hipotese.rodadas += 1
        if len(registro.vereditos) == antes:  # o validador não concluiu
            decisao, justificativa = "inconclusivo", "o validador não registrou veredito"
        else:
            decisao = registro.vereditos[-1].decisao
            justificativa = registro.vereditos[-1].justificativa
        if decisao == "confirmado":
            registro.situacao = "confirmado"
            registro.confianca = confianca(registro.vereditos[-1])  # type: ignore[assignment]
            hipotese.situacao = "confirmada"
        elif decisao == "descartado":
            registro.situacao = "descartado"
            hipotese.situacao = "descartada"
            hipotese.motivo = justificativa
        elif hipotese.rodadas < self._orcamento(estado).rodadas_validacao and registro.vereditos:
            # volta ao investigador com as pendências; só retorna à validação se ele revisar
            registro.situacao = "inconclusivo"
            hipotese.situacao = "candidata"
        else:
            registro.situacao = "inconclusivo"
            hipotese.situacao = "inconclusiva"
            hipotese.motivo = justificativa
        persistencia.salvar(pasta, estado)
        if decisao == "confirmado" and not self._esgotado(estado):
            contexto, _ = self._contexto()
            prompt = prompts.correlacionar(estado, registro, contexto)
            self._sessao(pasta, "investigador", "correlacionar", achado_id, prompt)

    def _fase_relatar(self, pasta: Path) -> None:
        estado = persistencia.carregar(pasta)
        if estado.achados or estado.hipoteses:
            prompt = prompts.relatar(estado)
            limite = CICLOS_RELATAR
            self._sessao(pasta, "investigador", "relatar", None, prompt, limite, limite)
            estado = persistencia.carregar(pasta)
            if estado.situacao == "pausada":
                return
        if estado.resumo is None:
            estado.resumo = resumo_automatico(estado)
        estado.situacao = "parcial" if estado.motivo_parada else "concluida"
        persistencia.salvar(pasta, estado)
        try:
            gerar(estado, pasta, self.deps.agora())
        except ErroRelatorio as erro:  # encerra mesmo assim, com o problema registrado
            estado.situacao = "parcial"
            estado.motivo_parada = f"relatório recusado: {erro}"
            persistencia.salvar(pasta, estado)
            (pasta / "relatorio-recusado.txt").write_text(str(erro), encoding="utf-8")
        self._transicao(pasta, "encerrar")

    def _consultas_chave(self, pasta: Path, citadas: set[str]) -> list[ConsultaChave]:
        diario = Diario(pasta)
        registros = diario.consultas()
        chaves = []
        for consulta_id in sorted(citadas, key=lambda c: int(c[1:])):
            if consulta_id in registros:
                tabela = pq.read_table(diario.caminho_resultado(consulta_id))
                chaves.append(
                    ConsultaChave(
                        sql=registros[consulta_id].sql, linhas=tabela.num_rows, soma=_somar(tabela)
                    )
                )
        return chaves

    def _fase_encerrar(self, pasta: Path) -> None:
        estado = persistencia.carregar(pasta)
        agora = self.deps.agora()
        for registro in estado.achados:
            citadas = {c for fato in registro.achado.fatos for c in fato.consultas}
            self.caderno.registrar(
                registro,
                estado.id,
                agora.date(),
                f"{estado.id}/relatorio.html",
                self._consultas_chave(pasta, citadas),
                agora,
            )
        gerar_indice(self.config.investigacoes)
        self._transicao(pasta, "concluida")
