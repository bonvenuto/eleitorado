import asyncio
from datetime import UTC, date, datetime

import pytest

from agente import estado as persistencia
from agente.config import ConfigAgente, Orcamento
from agente.modelos import Achado, Estado, Hipotese, NovaHipotese, Resumo, Veredito
from agente.servidor import (
    FERRAMENTAS_POR_PAPEL,
    ErroFerramenta,
    Ferramentas,
    Sessao,
    criar_servidor,
)

ORCAMENTO = Orcamento(ciclos=10, minutos=10, hipoteses=2, rodadas_validacao=2)


@pytest.fixture
def config(lago, tmp_path):
    return ConfigAgente(
        raiz=tmp_path,
        lago=lago,
        investigacoes=tmp_path / "investigacoes",
        prefixo_gcs="paralelo/",
        modelo=None,
        tempo_consulta_s=30,
        linhas_exibidas=20,
        linhas_salvas=1000,
        livre=ORCAMENTO,
        tema=ORCAMENTO,
    )


@pytest.fixture
def pasta(config):
    pasta = config.investigacoes / "inv1"
    estado = Estado(
        id="inv1",
        criada_em=datetime(2026, 10, 6, tzinfo=UTC),
        hipoteses=[Hipotese(id="h1", texto="Concentração de pagamentos", lente="c", prioridade=1)],
    )
    persistencia.salvar(pasta, estado)
    return pasta


def ferramentas(config, pasta, papel="investigador", fase="investigar", alvo="h1"):
    sessao = Sessao(pasta=pasta, papel=papel, fase=fase, alvo=alvo, config=config)
    return Ferramentas(sessao, hoje=lambda: date(2026, 10, 6))


def achado(**sobrescritas) -> Achado:
    base = {
        "hipotese_id": "h1",
        "tipo": "insight estratégico",
        "padrao": "concentracao",
        "titulo": "Três empresas concentram os pagamentos",
        "entidades": {"cnpj_raiz": ["11222333"]},
        "fatos": [{"texto": "300 fornecedores", "consultas": ["q1"]}],
    }
    return Achado.model_validate(base | sobrescritas)


def test_ferramentas_por_papel(config, pasta):
    for papel, esperadas in FERRAMENTAS_POR_PAPEL.items():
        servidor = criar_servidor(ferramentas(config, pasta, papel=papel))
        nomes = [t.name for t in asyncio.run(servidor.list_tools())]
        assert nomes == esperadas
    validador = criar_servidor(ferramentas(config, pasta, papel="validador"))
    nomes = [t.name for t in asyncio.run(validador.list_tools())]
    assert "achado_registrar" not in nomes


def test_esquema_do_achado_chega_ao_agente(config, pasta):
    servidor = criar_servidor(ferramentas(config, pasta))
    ferramenta = next(t for t in asyncio.run(servidor.list_tools()) if t.name == "achado_registrar")
    assert "fatos" in str(ferramenta.input_schema)


def test_consultar_e_registrar_achado(config, pasta):
    f = ferramentas(config, pasta)
    texto = f.consultar("select count(*) as n from marts.fornecedores")
    assert texto.startswith("Consulta q1: 1 linha(s)")
    assert f.achado_registrar(achado()) == "achado a1 registrado; segue para validação"
    estado = persistencia.carregar(pasta)
    assert estado.hipotese("h1").situacao == "candidata"
    assert estado.achado("a1").situacao == "em_validacao"
    # nova rodada substitui o achado da mesma hipótese
    f.achado_registrar(achado(titulo="Duas empresas concentram os pagamentos"))
    estado = persistencia.carregar(pasta)
    assert len(estado.achados) == 1
    assert estado.achado("a1").achado.titulo.startswith("Duas")


def test_achado_com_consulta_inexistente_e_recusado(config, pasta):
    with pytest.raises(ErroFerramenta, match="q1"):
        ferramentas(config, pasta).achado_registrar(achado())


def test_achado_de_outra_hipotese_e_recusado(config, pasta):
    f = ferramentas(config, pasta, alvo="h2")
    f.consultar("select 1")
    with pytest.raises(ErroFerramenta, match="h2"):
        f.achado_registrar(achado())


def test_escrita_fora_da_fase_e_recusada(config, pasta):
    f = ferramentas(config, pasta, fase="explorar", alvo=None)
    with pytest.raises(ErroFerramenta, match="investigar"):
        f.hipotese_descartar("sem dados")
    with pytest.raises(ErroFerramenta, match="relatar"):
        f.resumo_registrar(Resumo(texto="Nada relevante nesta investigação."))


def test_hipoteses_registrar_numera_em_sequencia(config, pasta):
    f = ferramentas(config, pasta, fase="explorar", alvo=None)
    nova = NovaHipotese(texto="Fracionamento de dispensas", lente="fracionamento", prioridade=2)
    assert f.hipoteses_registrar([nova, nova]) == "hipóteses registradas: h2, h3"
    assert [h.origem for h in persistencia.carregar(pasta).hipoteses] == ["exploracao"] * 3


def test_validador_registra_veredito(config, pasta):
    investigador = ferramentas(config, pasta)
    investigador.consultar("select 1")
    investigador.achado_registrar(achado())
    validador = ferramentas(config, pasta, papel="validador", fase="validar", alvo="a1")
    veredito = Veredito(decisao="descartado", justificativa="as empresas são do mesmo grupo")
    assert validador.veredito_registrar(veredito) == "veredito registrado para a1"
    assert persistencia.carregar(pasta).achado("a1").vereditos == [veredito]


def test_erro_da_ferramenta_chega_ao_agente(config, pasta):
    from mcp.server.mcpserver.exceptions import ToolError

    servidor = criar_servidor(ferramentas(config, pasta))
    with pytest.raises(ToolError, match="só SELECT"):
        asyncio.run(servidor.call_tool("consultar", {"sql": "delete from marts.tabela"}))


def test_caderno_buscar_e_aprender(config, pasta):
    f = ferramentas(config, pasta)
    assert f.caderno_buscar("11222333") == "nenhum caso com '11222333'"
    assert f.caderno_aprender("CODIGO_CAMARA não é CNPJ") == "aprendizado registrado"
    assert "inv1" in (config.caderno / "aprendizados.md").read_text(encoding="utf-8")


def test_na_fase_relatar_nao_ha_consulta_nova(config, pasta):
    f = ferramentas(config, pasta, fase="relatar", alvo=None)
    with pytest.raises(ErroFerramenta, match="já feitas"):
        f.consultar("select 1")
