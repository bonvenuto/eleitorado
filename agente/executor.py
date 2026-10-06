"""Sessões do Claude Code (`claude -p`) e o rastro do laço Sense-Think-Act.

Cada sessão roda um agente (investigador ou validador) com as ferramentas MCP do agente,
`WebSearch` e `WebFetch`, sem shell e sem acesso a arquivos. O controlador lê a saída
`stream-json` e grava cada passo em `ciclos.jsonl`:

- think: o texto do agente (o raciocínio que justifica a próxima ação);
- act: a chamada de ferramenta;
- sense: o resultado que volta para o agente.

O monitor encerra a sessão quando ela estoura o orçamento de ciclos ou de tempo, repete a mesma
ação, ou quando a assinatura atinge o limite de uso.
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import threading
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

Parada = Literal[
    "concluida", "orcamento_ciclos", "orcamento_tempo", "repeticao", "limite_uso", "erro"
]
TAMANHO_MAXIMO = 2000  # caracteres de cada passo guardados no rastro


@dataclass(frozen=True)
class Limites:
    ciclos: int  # chamadas de ferramenta nesta sessão
    segundos: float  # duração máxima desta sessão
    repeticoes: int = 3  # a mesma ação (ferramenta + entrada) repetida


@dataclass(frozen=True)
class PedidoSessao:
    agente: str  # investigador ou validador
    fase: str  # explorar, investigar, validar, correlacionar ou relatar
    alvo: str | None  # hipótese ou achado
    prompt: str
    pasta: Path  # investigacoes/<id>


@dataclass(frozen=True)
class ResultadoSessao:
    parada: Parada
    ciclos: int
    segundos: float
    texto_final: str = ""
    detalhe: str = ""


class Executor(Protocol):
    def rodar(self, pedido: PedidoSessao, limites: Limites) -> ResultadoSessao: ...


def _curto(valor: Any) -> str:
    texto = valor if isinstance(valor, str) else json.dumps(valor, ensure_ascii=False)
    return texto if len(texto) <= TAMANHO_MAXIMO else texto[:TAMANHO_MAXIMO] + "…"


class Monitor:
    """Consome os eventos `stream-json` de uma sessão, grava o rastro e decide se ela para."""

    def __init__(
        self,
        pedido: PedidoSessao,
        limites: Limites,
        agora: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.pedido = pedido
        self.limites = limites
        self.ciclos = 0
        self.texto_final = ""
        self.parada: Parada | None = None
        self.detalhe = ""
        self._acoes: Counter[str] = Counter()
        self._agora = agora
        self._rastro = pedido.pasta / "ciclos.jsonl"
        self._rastro.parent.mkdir(parents=True, exist_ok=True)

    def _gravar(self, etapa: str, conteudo: Any, ferramenta: str | None = None, **extra) -> None:
        registro = {
            "em": self._agora().isoformat(timespec="seconds"),
            "fase": self.pedido.fase,
            "alvo": self.pedido.alvo,
            "agente": self.pedido.agente,
            "etapa": etapa,
            "ferramenta": ferramenta,
            "conteudo": _curto(conteudo),
            **extra,
        }
        with self._rastro.open("a", encoding="utf-8") as saida:
            saida.write(json.dumps(registro, ensure_ascii=False) + "\n")

    def _parar(self, parada: Parada, detalhe: str) -> None:
        if self.parada is None:
            self.parada = parada
            self.detalhe = detalhe

    def evento(self, evento: dict[str, Any]) -> None:
        tipo = evento.get("type")
        if tipo == "rate_limit_event":
            info = evento.get("rate_limit_info") or {}
            if info.get("status") not in (None, "allowed", "allowed_warning"):
                self._parar("limite_uso", f"limite de uso: {info.get('rateLimitType')}")
            return
        if tipo == "result":
            self.texto_final = str(evento.get("result") or "")
            if evento.get("is_error"):
                texto = self.texto_final.lower()
                if "limit" in texto or "usage" in texto:
                    self._parar("limite_uso", self.texto_final[:200])
                else:
                    self._parar("erro", self.texto_final[:200] or str(evento.get("subtype")))
            else:
                self._parar("concluida", "")
            return
        if tipo not in ("assistant", "user"):
            return
        conteudo = (evento.get("message") or {}).get("content")
        if not isinstance(conteudo, list):
            return
        for bloco in conteudo:
            if bloco.get("type") == "text" and tipo == "assistant":
                self._gravar("think", bloco.get("text", ""))
            elif bloco.get("type") == "tool_use":
                self.ciclos += 1
                entrada = bloco.get("input", {})
                self._gravar("act", entrada, ferramenta=bloco.get("name"))
                chave = bloco.get("name", "") + json.dumps(entrada, sort_keys=True)
                self._acoes[chave] += 1
                if self._acoes[chave] >= self.limites.repeticoes:
                    self._parar("repeticao", f"ação repetida: {bloco.get('name')}")
                if self.ciclos >= self.limites.ciclos:
                    self._parar("orcamento_ciclos", f"{self.ciclos} ciclos")
            elif bloco.get("type") == "tool_result":
                self._gravar("sense", bloco.get("content"), erro=bool(bloco.get("is_error")))


def encerrar_processo(processo: subprocess.Popen) -> None:
    """Encerra o processo e os filhos (o servidor MCP), inclusive no Windows."""
    if processo.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(processo.pid)], capture_output=True, check=False
        )
    else:
        processo.kill()
    try:
        processo.wait(timeout=30)
    except subprocess.TimeoutExpired:
        processo.kill()


class ExecutorClaude:
    """Executa `claude -p` com o agente, as permissões fechadas e o servidor MCP do agente."""

    def __init__(
        self,
        raiz: Path,
        modelo: str | None = None,
        comando: list[str] | None = None,
        arquivo_config: Path | None = None,
    ) -> None:
        self.raiz = raiz
        self.modelo = modelo
        self.arquivo_config = arquivo_config
        # caminho completo: no Windows o subprocess não acha `claude` sem a extensão
        self.comando = comando or [shutil.which("claude") or "claude"]

    def configuracao_mcp(self, pedido: PedidoSessao) -> dict[str, Any]:
        return {
            "mcpServers": {
                "agente": {
                    "command": "uv",
                    "args": ["run", "--project", str(self.raiz), "python", "-m", "agente.servidor"],
                    "env": {
                        "AGENTE_INVESTIGACAO": str(pedido.pasta.resolve()),
                        "AGENTE_PAPEL": pedido.agente,
                        "AGENTE_FASE": pedido.fase,
                        "AGENTE_ALVO": pedido.alvo or "",
                        "AGENTE_CONFIG": str(self.arquivo_config or ""),
                    },
                }
            }
        }

    def comando_sessao(self, pedido: PedidoSessao, arquivo_mcp: Path) -> list[str]:
        comando = [
            *self.comando,
            "-p",
            "--agent",
            pedido.agente,
            "--settings",
            str(self.raiz / "agente" / "permissoes.json"),
            "--setting-sources",
            "project",
            "--mcp-config",
            str(arquivo_mcp),
            "--strict-mcp-config",
            "--permission-mode",
            "dontAsk",
            "--output-format",
            "stream-json",
            "--verbose",
            "--no-session-persistence",
        ]
        if self.modelo:
            comando += ["--model", self.modelo]
        return comando

    def rodar(self, pedido: PedidoSessao, limites: Limites) -> ResultadoSessao:
        sessoes = pedido.pasta / "sessoes"
        sessoes.mkdir(parents=True, exist_ok=True)
        numero = len(list(sessoes.glob("*.mcp.json"))) + 1
        arquivo_mcp = sessoes / f"{numero:03d}-{pedido.fase}.mcp.json"
        arquivo_mcp.write_text(
            json.dumps(self.configuracao_mcp(pedido), indent=1), encoding="utf-8"
        )
        monitor = Monitor(pedido, limites)
        inicio = time.monotonic()
        erros = arquivo_mcp.with_name(arquivo_mcp.name.replace(".mcp.json", ".stderr.txt"))
        saida_erro = erros.open(
            "w", encoding="utf-8"
        )  # em arquivo: um pipe cheio travaria a sessão
        processo = subprocess.Popen(
            self.comando_sessao(pedido, arquivo_mcp),
            cwd=self.raiz,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=saida_erro,
            text=True,
            encoding="utf-8",
        )
        assert processo.stdin is not None and processo.stdout is not None
        processo.stdin.write(pedido.prompt)  # pela entrada: o prompt pode passar do limite da linha
        processo.stdin.close()
        linhas: queue.Queue[str | None] = queue.Queue()

        def ler() -> None:
            assert processo.stdout is not None
            for linha in processo.stdout:
                linhas.put(linha)
            linhas.put(None)

        threading.Thread(target=ler, daemon=True).start()
        while monitor.parada is None:
            restante = limites.segundos - (time.monotonic() - inicio)
            if restante <= 0:
                monitor._parar("orcamento_tempo", f"{limites.segundos:.0f} s")
                break
            try:
                linha = linhas.get(timeout=min(restante, 5))
            except queue.Empty:
                continue
            if linha is None:
                break
            if linha.strip():
                try:
                    monitor.evento(json.loads(linha))
                except json.JSONDecodeError:
                    continue
        encerrar_processo(processo)
        saida_erro.close()
        if monitor.parada is None:
            erro = erros.read_text(encoding="utf-8", errors="replace")
            monitor._parar("erro", f"a sessão terminou sem resultado: {erro[:300]}")
        return ResultadoSessao(
            parada=monitor.parada or "erro",
            ciclos=monitor.ciclos,
            segundos=round(time.monotonic() - inicio, 1),
            texto_final=monitor.texto_final,
            detalhe=monitor.detalhe,
        )
