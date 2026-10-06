import io
import json

import pytest

from agente.hook_web import main, motivo_bloqueio


@pytest.mark.parametrize(
    "texto",
    ["CPF 123.456.789-09", "12345678909 situação", "123 456 789 09", "processo 23238003685/2026"],
)
def test_bloqueia_onze_digitos(texto):
    assert motivo_bloqueio({"tool_name": "WebSearch", "tool_input": {"query": texto}})


@pytest.mark.parametrize(
    "texto",
    [
        "CNPJ 00.000.000/0001-91 Banco do Brasil",
        "00000000000191",
        "contratos ministério da saúde 2025",
        "telefone (11) 91234-5678",
    ],
)
def test_deixa_passar(texto):
    assert motivo_bloqueio({"tool_name": "WebSearch", "tool_input": {"query": texto}}) is None


def test_webfetch_olha_a_url():
    evento = {"tool_name": "WebFetch", "tool_input": {"url": "https://x.com/?cpf=12345678909"}}
    assert motivo_bloqueio(evento)


def test_main_codigos_de_saida():
    erro = io.StringIO()
    bloqueio = json.dumps({"tool_input": {"query": "123.456.789-09"}})
    assert main(io.StringIO(bloqueio), erro) == 2
    assert "bloqueado" in erro.getvalue()
    assert main(io.StringIO(json.dumps({"tool_input": {"query": "ok"}})), io.StringIO()) == 0
    assert main(io.StringIO("não é json"), io.StringIO()) == 2
