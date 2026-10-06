import json
from datetime import UTC, datetime, timedelta

import pytest

from agente import estado as persistencia
from agente.caderno import Caderno, Caso
from agente.config import ConfigAgente, Orcamento
from agente.controlador import Controlador, Dependencias, ErroTrava, identificador, trava
from agente.executor import ResultadoSessao
from agente.modelos import Achado, NovaHipotese, Resumo, Veredito
from agente.preparar import Preparo
from agente.servidor import Ferramentas, Sessao

AGORA = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)


def config_de(lago, tmp_path, ciclos=60, rodadas=2) -> ConfigAgente:
    orcamento = Orcamento(ciclos=ciclos, minutos=90, hipoteses=3, rodadas_validacao=rodadas)
    return ConfigAgente(
        raiz=tmp_path,
        lago=lago,
        investigacoes=tmp_path / "investigacoes",
        prefixo_gcs="paralelo/",
        modelo=None,
        tempo_consulta_s=30,
        linhas_exibidas=20,
        linhas_salvas=1000,
        livre=orcamento,
        tema=orcamento,
    )


def achado(hipotese_id: str, consulta: str) -> Achado:
    return Achado(
        hipotese_id=hipotese_id,
        tipo="situação suspeita",
        padrao="concentracao",
        titulo="Empresa 7 concentra os pagamentos",
        entidades={"fornecedor": ["empresa 7"]},
        fatos=[{"texto": "A empresa 7 recebeu o maior valor", "consultas": [consulta]}],
    )


def veredito(decisao: str) -> Veredito:
    extra = {"pendencias": ["checar 2024"]} if decisao == "inconclusivo" else {}
    alternativas = [{"explicacao": "contrato único", "resultado": "não explica"}]
    return Veredito(
        decisao=decisao, justificativa="testado contra os dados", alternativas=alternativas, **extra
    )


class ExecutorFalso:
    """Faz o papel do Claude: chama as ferramentas do servidor conforme um roteiro por fase."""

    def __init__(self, config, roteiro, ciclos=None):
        self.config = config
        self.roteiro = roteiro
        self.ciclos = ciclos or {}  # ciclos gastos por fase (padrão 3)
        self.pedidos = []
        self.limites = []

    def rodar(self, pedido, limites):
        self.pedidos.append(pedido)
        self.limites.append(limites)
        sessao = Sessao(pedido.pasta, pedido.agente, pedido.fase, pedido.alvo, self.config)
        ferramentas = Ferramentas(sessao)
        acao = self.roteiro.get((pedido.fase, pedido.alvo)) or self.roteiro.get(pedido.fase)
        if isinstance(acao, list):  # uma ação por chamada, em sequência
            acao = acao.pop(0)
        parada = acao(ferramentas) if acao else "concluida"
        ciclos = self.ciclos.get(pedido.fase, 3)
        return ResultadoSessao(parada=parada or "concluida", ciclos=ciclos, segundos=10.0)


def explorar(f):
    f.hipoteses_registrar(
        [
            NovaHipotese(texto="Concentração de pagamentos", lente="concentração", prioridade=1),
            NovaHipotese(texto="Fracionamento de compras", lente="fracionamento", prioridade=2),
        ]
    )


def investigar_h1(f):
    f.consultar("select nome, valor from marts.fornecedores order by valor desc limit 3")
    f.achado_registrar(achado("h1", "q1"))


def preparo():
    return Preparo(versao_dados={"lago": "abc"}, dbt_rodou=False, revisar=[])


@pytest.fixture
def montar(lago, tmp_path):
    def _montar(roteiro, ciclos_por_fase=None, **opcoes):
        config = config_de(lago, tmp_path, **opcoes)
        executor = ExecutorFalso(config, roteiro, ciclos_por_fase)
        controlador = Controlador(Dependencias(config, executor, preparo, lambda: AGORA))
        return controlador, executor, config

    return _montar


def test_identificador():
    assert identificador(AGORA, None) == "20261006-0900-livre"
    assert (
        identificador(AGORA, "Emendas pagas no PI em 2025!")
        == "20261006-0900-emendas-pagas-no-pi-em-2025"
    )


def test_fluxo_completo(montar):
    roteiro = {
        "explorar": explorar,
        ("investigar", "h1"): investigar_h1,
        ("investigar", "h2"): lambda f: f.hipotese_descartar("as compras estão acima do limite"),
        "validar": lambda f: f.veredito_registrar(veredito("confirmado")),
        "correlacionar": lambda f: f.correlacionados_registrar([]),
        "relatar": lambda f: f.resumo_registrar(
            Resumo(texto="Uma empresa concentra os pagamentos.")
        ),
    }
    controlador, executor, config = montar(roteiro)
    estado = controlador.executar(controlador.nova(None))
    assert (estado.fase, estado.situacao) == ("concluida", "concluida")
    assert [(p.fase, p.alvo, p.agente) for p in executor.pedidos] == [
        ("explorar", None, "investigador"),
        ("investigar", "h1", "investigador"),
        ("validar", "a1", "validador"),
        ("correlacionar", "a1", "investigador"),
        ("investigar", "h2", "investigador"),
        ("relatar", None, "investigador"),
    ]
    registro = estado.achado("a1")
    assert (registro.situacao, registro.confianca) == ("confirmado", "média")
    assert estado.hipotese("h2").situacao == "descartada"
    assert estado.versao_dados == {"lago": "abc"}
    assert (estado.uso.sessoes, estado.uso.ciclos, estado.uso.consultas) == (6, 18, 1)
    pasta = config.investigacoes / estado.id
    assert (pasta / "relatorio.html").exists() and (config.investigacoes / "index.html").exists()
    [caso] = Caderno(config.caderno).listar("confirmado")
    assert caso.consultas_chave[0].linhas == 3
    assert [t.fase for t in estado.transicoes] == [
        "explorar",
        "investigar",
        "relatar",
        "encerrar",
        "concluida",
    ]


def test_inconclusivo_volta_ao_investigador_com_as_pendencias(montar):
    roteiro = {
        "explorar": lambda f: f.hipoteses_registrar(
            [NovaHipotese(texto="Concentração de pagamentos", lente="c", prioridade=1)]
        ),
        ("investigar", "h1"): [investigar_h1, investigar_h1],
        "validar": [
            lambda f: f.veredito_registrar(veredito("inconclusivo")),
            lambda f: f.veredito_registrar(veredito("confirmado")),
        ],
    }
    controlador, executor, _ = montar(roteiro)
    estado = controlador.executar(controlador.nova(None))
    fases = [p.fase for p in executor.pedidos]
    assert fases == [
        "explorar",
        "investigar",
        "validar",
        "investigar",
        "validar",
        "correlacionar",
        "relatar",
    ]
    assert "checar 2024" in executor.pedidos[3].prompt
    assert estado.achado("a1").situacao == "confirmado"
    assert estado.hipotese("h1").rodadas == 2


def test_inconclusivo_sem_rodadas_fica_inconclusivo(montar):
    roteiro = {
        "explorar": lambda f: f.hipoteses_registrar(
            [NovaHipotese(texto="Concentração de pagamentos", lente="c", prioridade=1)]
        ),
        ("investigar", "h1"): investigar_h1,
        "validar": lambda f: f.veredito_registrar(veredito("inconclusivo")),
    }
    controlador, _, _ = montar(roteiro, rodadas=1)
    estado = controlador.executar(controlador.nova(None))
    assert estado.achado("a1").situacao == "inconclusivo"
    assert estado.hipotese("h1").situacao == "inconclusiva"


def test_sessao_sem_conclusao(montar):
    roteiro = {
        "explorar": lambda f: f.hipoteses_registrar(
            [NovaHipotese(texto="Concentração de pagamentos", lente="c", prioridade=1)]
        ),
        ("investigar", "h1"): lambda f: "orcamento_ciclos",
    }
    controlador, _, _ = montar(roteiro)
    estado = controlador.executar(controlador.nova(None))
    assert estado.hipotese("h1").situacao == "inconclusiva"
    assert "orcamento_ciclos" in estado.hipotese("h1").motivo


def test_limite_de_uso_pausa_e_retoma_sem_refazer(montar):
    chamadas = {"investigar": 0}

    def investigar(f):
        chamadas["investigar"] += 1
        if chamadas["investigar"] == 1:
            return "limite_uso"
        investigar_h1(f)
        return None

    roteiro = {
        "explorar": lambda f: f.hipoteses_registrar(
            [NovaHipotese(texto="Concentração de pagamentos", lente="c", prioridade=1)]
        ),
        ("investigar", "h1"): investigar,
        "validar": lambda f: f.veredito_registrar(veredito("descartado")),
    }
    controlador, executor, _ = montar(roteiro)
    pasta = controlador.nova(None)
    estado = controlador.executar(pasta)
    assert (estado.situacao, estado.fase) == ("pausada", "investigar")
    assert controlador.pendente() == pasta
    estado = controlador.executar(pasta)
    assert estado.situacao == "concluida"
    assert [p.fase for p in executor.pedidos].count("explorar") == 1
    assert estado.achado("a1").situacao == "descartado"


def test_orcamento_esgotado_relata_parcial(montar):
    roteiro = {"explorar": explorar}
    controlador, executor, config = montar(roteiro, ciclos=3)
    estado = controlador.executar(controlador.nova("concentração"))
    assert estado.situacao == "parcial"
    assert "ciclos" in estado.motivo_parada
    assert [p.fase for p in executor.pedidos] == ["explorar", "relatar"]  # o resumo sempre sai
    assert executor.limites[-1].ciclos == 10
    assert (config.investigacoes / estado.id / "relatorio.html").exists()


def test_caderno_entra_na_fila_da_investigacao_livre(montar, tmp_path):
    caso = Caso(
        caso_id="c1",
        titulo="ACME sancionada",
        tipo="situação suspeita",
        padrao="p",
        entidades={"cnpj_raiz": ["11222333"]},
        situacao="confirmado",
        atualizado_em=AGORA,
    )
    controlador, executor, _ = montar({})
    controlador.deps.preparar = lambda: Preparo(versao_dados={}, dbt_rodou=False, revisar=[caso])
    estado = controlador.executar(controlador.nova(None))
    assert estado.hipoteses[0].origem == "caderno" and estado.hipoteses[0].caso_id == "c1"
    assert executor.pedidos[1].alvo == "h1"


def test_trava(tmp_path):
    with trava(tmp_path, AGORA):
        with pytest.raises(ErroTrava):
            with trava(tmp_path, AGORA + timedelta(hours=1)):
                pass
    assert not (tmp_path / ".trava").exists()
    (tmp_path / ".trava").write_text(json.dumps({"pid": 1, "desde": AGORA.isoformat()}), "utf-8")
    with trava(tmp_path, AGORA + timedelta(hours=7)):  # trava órfã
        pass


def test_retoma_investigacao_com_achado_registrado_e_sem_veredito(montar):
    roteiro = {"validar": lambda f: f.veredito_registrar(veredito("confirmado"))}
    controlador, executor, config = montar(roteiro)
    pasta = controlador.nova(None)
    estado = persistencia.carregar(pasta)
    estado.fase = "investigar"
    persistencia.salvar(pasta, estado)
    f = Ferramentas(Sessao(pasta, "investigador", "explorar", None, config))
    f.hipoteses_registrar(
        [NovaHipotese(texto="Concentração de pagamentos", lente="c", prioridade=1)]
    )
    f = Ferramentas(Sessao(pasta, "investigador", "investigar", "h1", config))
    f.consultar("select 1")
    f.achado_registrar(achado("h1", "q1"))
    estado = controlador.executar(pasta)
    assert [p.fase for p in executor.pedidos][:1] == ["validar"]  # não refaz a investigação
    assert estado.achado("a1").situacao == "confirmado"


def test_reserva_impede_comecar_hipotese_sem_ciclos(montar):
    controlador, executor, _ = montar({"explorar": explorar}, ciclos=22)
    estado = controlador.executar(controlador.nova(None))
    assert [p.fase for p in executor.pedidos] == ["explorar", "relatar"]
    assert "não bastam" in estado.motivo_parada and estado.situacao == "parcial"


def test_achado_registrado_e_validado_mesmo_com_o_orcamento_no_fim(montar):
    roteiro = {
        "explorar": lambda f: f.hipoteses_registrar(
            [NovaHipotese(texto="Concentração de pagamentos", lente="c", prioridade=1)]
        ),
        ("investigar", "h1"): investigar_h1,
        "validar": lambda f: f.veredito_registrar(veredito("confirmado")),
    }
    controlador, executor, _ = montar(roteiro, {"investigar": 25}, ciclos=30)
    estado = controlador.executar(controlador.nova(None))
    fases = [p.fase for p in executor.pedidos]
    assert fases == [
        "explorar",
        "investigar",
        "validar",
        "relatar",
    ]  # sem ciclos para correlacionar
    assert executor.limites[2].ciclos == 12  # mínimo da validação, acima do que restava (2)
    assert estado.achado("a1").situacao == "confirmado"


def test_resumo_automatico_quando_o_agente_nao_registra(montar):
    roteiro = {
        "explorar": lambda f: f.hipoteses_registrar(
            [NovaHipotese(texto="Concentração de pagamentos", lente="c", prioridade=1)]
        ),
        ("investigar", "h1"): investigar_h1,
        "validar": lambda f: f.veredito_registrar(veredito("confirmado")),
        "relatar": lambda f: "orcamento_ciclos",  # gasta a sessão e não registra o resumo
    }
    controlador, executor, _ = montar(roteiro)
    estado = controlador.executar(controlador.nova(None))
    assert executor.limites[-1].ciclos == 10
    assert "relatar" in executor.pedidos[-1].fase and "q1" in executor.pedidos[-1].prompt
    assert estado.resumo is not None
    assert estado.resumo.texto.startswith("Resumo automático")
    assert "Empresa 7 concentra os pagamentos" in estado.resumo.texto


def test_descarta_investigacao_que_nao_comecou(montar):
    controlador, _, config = montar({})
    pasta = controlador.nova("tema qualquer")
    assert controlador.descartar_se_nao_comecou(pasta)
    assert not pasta.exists()
    outra = controlador.nova(None)
    controlador.executar(outra)  # já passou da preparação: não é descartada
    assert not controlador.descartar_se_nao_comecou(outra)
    assert outra.exists()
