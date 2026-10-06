import json
import sys
from pathlib import Path

from agente.executor import ExecutorClaude, Limites, Monitor, PedidoSessao


def pedido(pasta: Path, prompt: str = "investigue") -> PedidoSessao:
    return PedidoSessao(
        agente="investigador", fase="investigar", alvo="h1", prompt=prompt, pasta=pasta
    )


def assistente(*blocos):
    return {"type": "assistant", "message": {"content": list(blocos)}}


def texto(t):
    return {"type": "text", "text": t}


def uso(nome, entrada, id_="t1"):
    return {"type": "tool_use", "id": id_, "name": nome, "input": entrada}


def resultado_ferramenta(conteudo, erro=False, id_="t1"):
    return {
        "type": "user",
        "message": {
            "content": [
                {"type": "tool_result", "tool_use_id": id_, "content": conteudo, "is_error": erro}
            ]
        },
    }


def final(texto_final="pronto", erro=False):
    return {"type": "result", "subtype": "success", "is_error": erro, "result": texto_final}


def rastro(pasta: Path) -> list[dict]:
    linhas = (pasta / "ciclos.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(linha) for linha in linhas]


def test_grava_think_act_sense_e_conclui(tmp_path):
    monitor = Monitor(pedido(tmp_path), Limites(ciclos=10, segundos=60))
    for evento in [
        {"type": "system", "subtype": "init"},
        assistente(texto("Vou medir a concentração."), uso("mcp__agente__consultar", {"sql": "s"})),
        resultado_ferramenta("Consulta q1: 3 linha(s)"),
        final("achado registrado"),
    ]:
        monitor.evento(evento)
    assert (monitor.parada, monitor.ciclos, monitor.texto_final) == (
        "concluida",
        1,
        "achado registrado",
    )
    passos = rastro(tmp_path)
    assert [p["etapa"] for p in passos] == ["think", "act", "sense"]
    assert passos[1]["ferramenta"] == "mcp__agente__consultar"
    assert (passos[0]["fase"], passos[0]["alvo"], passos[0]["agente"]) == (
        "investigar",
        "h1",
        "investigador",
    )


def test_estouro_de_ciclos(tmp_path):
    monitor = Monitor(pedido(tmp_path), Limites(ciclos=2, segundos=60))
    monitor.evento(assistente(uso("a", {"x": 1}, "t1"), uso("a", {"x": 2}, "t2")))
    assert monitor.parada == "orcamento_ciclos"


def test_repeticao_da_mesma_acao(tmp_path):
    monitor = Monitor(pedido(tmp_path), Limites(ciclos=50, segundos=60, repeticoes=3))
    for _ in range(2):
        monitor.evento(assistente(uso("mcp__agente__consultar", {"sql": "select 1"})))
    assert monitor.parada is None
    monitor.evento(assistente(uso("mcp__agente__consultar", {"sql": "select 1"})))
    assert monitor.parada == "repeticao"


def test_limite_de_uso(tmp_path):
    monitor = Monitor(pedido(tmp_path), Limites(ciclos=50, segundos=60))
    monitor.evento({"type": "rate_limit_event", "rate_limit_info": {"status": "allowed"}})
    assert monitor.parada is None
    monitor.evento(
        {
            "type": "rate_limit_event",
            "rate_limit_info": {"status": "rejected", "rateLimitType": "five_hour"},
        }
    )
    assert monitor.parada == "limite_uso"
    outro = Monitor(pedido(tmp_path / "b"), Limites(ciclos=50, segundos=60))
    outro.evento(final("Claude AI usage limit reached", erro=True))
    assert outro.parada == "limite_uso"


def test_erro_no_resultado(tmp_path):
    monitor = Monitor(pedido(tmp_path), Limites(ciclos=50, segundos=60))
    monitor.evento(final("falha interna", erro=True))
    assert (monitor.parada, monitor.detalhe) == ("erro", "falha interna")


def test_conteudo_longo_e_truncado(tmp_path):
    monitor = Monitor(pedido(tmp_path), Limites(ciclos=50, segundos=60))
    monitor.evento(assistente(texto("x" * 5000)))
    assert len(rastro(tmp_path)[0]["conteudo"]) == 2001


def falso_claude(tmp_path: Path, eventos: list[dict], espera: float = 0) -> list[str]:
    """Script que ignora os argumentos, confere o prompt e imprime os eventos."""
    script = tmp_path / "falso_claude.py"
    linhas = "\n".join(json.dumps(e) for e in eventos)
    script.write_text(
        "import sys, time\n"
        "prompt = sys.stdin.read()\n"
        "assert prompt == 'investigue', prompt\n"
        f"time.sleep({espera})\n"
        f"print({linhas!r}, flush=True)\n"
        "time.sleep(60 if '--travar' in sys.argv else 0)\n",
        encoding="utf-8",
    )
    return [sys.executable, str(script)]


def test_executor_roda_o_processo_e_le_o_rastro(tmp_path):
    eventos = [assistente(texto("ok"), uso("mcp__agente__consultar", {"sql": "s"})), final("fim")]
    executor = ExecutorClaude(tmp_path, comando=falso_claude(tmp_path, eventos))
    pasta = tmp_path / "investigacoes" / "inv1"
    resultado = executor.rodar(pedido(pasta), Limites(ciclos=10, segundos=60))
    assert (resultado.parada, resultado.ciclos, resultado.texto_final) == ("concluida", 1, "fim")
    configuracao = json.loads(next((pasta / "sessoes").glob("*.mcp.json")).read_text("utf-8"))
    ambiente = configuracao["mcpServers"]["agente"]["env"]
    assert (ambiente["AGENTE_PAPEL"], ambiente["AGENTE_FASE"], ambiente["AGENTE_ALVO"]) == (
        "investigador",
        "investigar",
        "h1",
    )


def test_executor_encerra_por_tempo(tmp_path):
    executor = ExecutorClaude(tmp_path, comando=[*falso_claude(tmp_path, [], espera=30)])
    resultado = executor.rodar(pedido(tmp_path / "inv"), Limites(ciclos=10, segundos=1))
    assert resultado.parada == "orcamento_tempo"
    assert resultado.segundos < 25


def test_executor_sem_resultado_e_erro(tmp_path):
    executor = ExecutorClaude(tmp_path, comando=falso_claude(tmp_path, [texto("sem fim")]))
    resultado = executor.rodar(pedido(tmp_path / "inv"), Limites(ciclos=10, segundos=30))
    assert resultado.parada == "erro"


def test_comando_da_sessao(tmp_path):
    executor = ExecutorClaude(tmp_path, modelo="opus")
    comando = executor.comando_sessao(pedido(tmp_path), tmp_path / "x.mcp.json")
    assert Path(comando[0]).stem.lower() == "claude"
    assert comando[1:4] == ["-p", "--agent", "investigador"]
    for par in (
        ["--permission-mode", "dontAsk"],
        ["--output-format", "stream-json"],
        ["--model", "opus"],
    ):
        indice = comando.index(par[0])
        assert comando[indice : indice + 2] == par
    assert "--strict-mcp-config" in comando
    assert "--no-session-persistence" in comando
