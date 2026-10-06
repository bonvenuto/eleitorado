from datetime import UTC, date, datetime

from agente.caderno import Caderno, ConsultaChave, caso_id, mudou
from agente.modelos import Achado, RegistroAchado, Veredito

AGORA = datetime(2026, 10, 6, 12, tzinfo=UTC)


def registro(situacao="confirmado", entidades=None) -> RegistroAchado:
    achado = Achado(
        hipotese_id="h1",
        tipo="situação suspeita",
        padrao="fornecedor_sancionado",
        titulo="ACME recebeu emendas durante a sanção",
        entidades=entidades or {"cnpj_raiz": ["11222333"], "orgao": ["Ministério X"]},
        fatos=[{"texto": "R$ 1,2 mi pagos", "consultas": ["q1"]}],
    )
    veredito = Veredito(
        decisao="confirmado",
        justificativa="CNPJ idêntico ao do CEIS e pagamentos na vigência",
        alternativas=[{"explicacao": "homônimo", "resultado": "CNPJ idêntico"}],
    )
    return RegistroAchado(
        id="a1", achado=achado, vereditos=[veredito], situacao=situacao, confianca="média"
    )


def test_caso_id_estavel_na_ordem_das_entidades():
    a = caso_id("p", {"orgao": ["B", "a"], "cnpj_raiz": ["1"]})
    b = caso_id("p", {"cnpj_raiz": ["1"], "orgao": ["A", "b"]})
    assert a == b
    assert a != caso_id("outro", {"cnpj_raiz": ["1"], "orgao": ["A", "b"]})


def test_registrar_cria_e_atualiza_o_mesmo_caso(tmp_path):
    caderno = Caderno(tmp_path)
    chave = [ConsultaChave(sql="select 1", linhas=3, soma=10.0)]
    primeiro = caderno.registrar(
        registro(), "inv1", date(2026, 10, 6), "inv1/relatorio.html", chave, AGORA
    )
    segundo = caderno.registrar(
        registro("descartado", {"orgao": ["Ministério X"], "cnpj_raiz": ["11222333"]}),
        "inv2",
        date(2026, 10, 13),
        "inv2/relatorio.html",
        [],
        AGORA,
    )
    assert primeiro.caso_id == segundo.caso_id
    caso = caderno.obter(primeiro.caso_id)
    assert caso.situacao == "descartado"
    assert [h.investigacao for h in caso.historico] == ["inv1", "inv2"]
    assert caso.consultas_chave == chave  # mantém as consultas-chave anteriores
    assert caderno.listar("descartado") == [caso]
    assert caderno.listar("confirmado") == []


def test_buscar_por_termo_cnpj_e_raiz(tmp_path):
    caderno = Caderno(tmp_path)
    caderno.registrar(registro(), "inv1", date(2026, 10, 6), "r.html", [], AGORA)
    assert len(caderno.buscar("11.222.333/0001-81")) == 1  # CNPJ acha a raiz
    assert len(caderno.buscar("acme")) == 1
    assert len(caderno.buscar("ministério x")) == 1
    assert caderno.buscar("99999999") == []


def test_mudanca_relevante():
    anterior = ConsultaChave(sql="s", linhas=10, soma=100.0)
    assert not mudou(anterior, 10, 105.0)
    assert mudou(anterior, 10, 111.0)
    assert mudou(anterior, 11, 100.0)
    assert mudou(ConsultaChave(sql="s", linhas=1, soma=0.0), 1, 5.0)
    assert not mudou(ConsultaChave(sql="s", linhas=1, soma=None), 1, None)


def test_aprendizados(tmp_path):
    caderno = Caderno(tmp_path)
    assert caderno.aprendizados() == ""
    caderno.aprender("CODIGO_CAMARA não é\nCNPJ", "inv1", date(2026, 10, 6))
    caderno.aprender("Senado publica CPF mascarado", "inv2", date(2026, 10, 7))
    texto = caderno.aprendizados()
    assert texto.startswith("# Aprendizados")
    assert "- CODIGO_CAMARA não é CNPJ _(investigação inv1, 2026-10-06)_" in texto
    assert texto.count("\n- ") == 2
