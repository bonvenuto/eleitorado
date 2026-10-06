import json
import re
from datetime import UTC, datetime

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from agente import graficos
from agente.diario import Diario, RegistroConsulta
from agente.modelos import Achado, Estado, Grafico, Hipotese, RegistroAchado, Resumo, Veredito
from agente.relatorio import ErroRelatorio, confianca, gerar, gerar_indice, montar, validar

AGORA = datetime(2026, 10, 6, 12, tzinfo=UTC)


def gravar_consulta(diario: Diario, consulta_id: str, tabela: pa.Table) -> None:
    destino = diario.caminho_resultado(consulta_id)
    destino.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(tabela, destino)
    diario.registrar(
        RegistroConsulta(
            id=consulta_id,
            sql=f"select * from x -- {consulta_id}",
            linhas=tabela.num_rows,
            truncada=False,
            colunas=tabela.column_names,
            sha256="0",
            executada_em="2026-10-06T12:00:00+00:00",
            duracao_s=0.1,
            papel="investigador",
        )
    )


def veredito(decisao="confirmado", corroborado=False) -> Veredito:
    extra = {}
    if corroborado:
        extra["fontes_web"] = [
            {
                "url": "https://portaldatransparencia.gov.br/sancoes/ceis/1",
                "titulo": "CEIS",
                "acessado_em": "2026-10-06",
                "trecho": "Impedimento de contratar",
            }
        ]
    if decisao == "inconclusivo":
        extra["pendencias"] = ["checar pagamentos de 2024"]
    return Veredito(
        decisao=decisao,
        justificativa="O CNPJ é o mesmo do cadastro e a vigência cobre os pagamentos",
        alternativas=[
            {"explicacao": "homônimo", "resultado": "CNPJ idêntico", "consultas": ["q1"]}
        ],
        corroboracao_independente=corroborado,
        **extra,
    )


def achado(hipotese_id: str, graficos_=()) -> Achado:
    return Achado(
        hipotese_id=hipotese_id,
        tipo="situação suspeita",
        padrao="fornecedor_sancionado",
        titulo="ACME recebeu pagamentos durante a sanção",
        entidades={"cnpj_raiz": ["11222333"]},
        fatos=[{"texto": "Pagamentos ao CPF 123.456.789-09 somam R$ 1,2 mi", "consultas": ["q1"]}],
        graficos=list(graficos_),
    )


@pytest.fixture
def investigacao(tmp_path):
    pasta = tmp_path / "investigacoes" / "inv1"
    diario = Diario(pasta)
    gravar_consulta(
        diario,
        "q1",
        pa.table(
            {
                "orgao": ["Ministério A", "Ministério B", "O'Brien Ltda"],
                "fornecedor": ["ACME", "ACME", "BETA"],
                "valor": [1000.5, 200.0, 30.0],
            }
        ),
    )
    graficos_ = [
        Grafico(
            tipo="barras",
            titulo="Pagos por órgão",
            consulta="q1",
            x="orgao",
            y="valor",
            destaque="O'Brien Ltda",
        ),
        Grafico(
            tipo="rede",
            titulo="Relações",
            consulta="q1",
            origem="orgao",
            destino="fornecedor",
            peso="valor",
        ),
        Grafico(tipo="tabela", titulo="Detalhe", consulta="q1"),
    ]
    estado = Estado(
        id="inv1",
        criada_em=AGORA,
        situacao="concluida",
        versao_dados={"manifesto": "2026-10-06"},
        hipoteses=[
            Hipotese(id="h1", texto="ACME sancionada recebeu", lente="sancoes", prioridade=1),
            Hipotese(id="h2", texto="Concentração em BETA", lente="concentracao", prioridade=2),
            Hipotese(
                id="h3",
                texto="Fracionamento de dispensas",
                lente="fracionamento",
                prioridade=3,
                situacao="descartada",
                motivo="valores acima do limite",
            ),
        ],
        achados=[
            RegistroAchado(
                id="a1",
                achado=achado("h1", graficos_),
                vereditos=[veredito(corroborado=True)],
                situacao="confirmado",
                confianca="alta",
            ),
            RegistroAchado(
                id="a2",
                achado=achado("h2"),
                vereditos=[veredito("inconclusivo")],
                situacao="inconclusivo",
            ),
        ],
        resumo=Resumo(
            texto="Uma empresa sancionada recebeu pagamentos de dois órgãos.",
            destaques=[{"texto": "R$ 1,2 mi", "consultas": ["q1"]}],
        ),
    )
    return pasta, estado


def test_confianca():
    assert confianca(veredito(corroborado=True)) == "alta"
    assert confianca(veredito()) == "média"


def test_montar_separa_as_secoes(investigacao):
    pasta, estado = investigacao
    relatorio = montar(estado, pasta, AGORA)
    assert [r["id"] for r in relatorio["achados"]] == ["a1"]
    assert [r["id"] for r in relatorio["inconclusivos"]] == ["a2"]
    assert [h["id"] for h in relatorio["hipoteses_descartadas"]] == ["h3"]
    assert list(relatorio["consultas"]) == ["q1"]
    validar(relatorio)


def test_validar_recusa_suspeita_sem_veredito_confirmado(investigacao):
    pasta, estado = investigacao
    relatorio = montar(estado, pasta, AGORA)
    relatorio["achados"][0]["vereditos"] = []
    with pytest.raises(ErroRelatorio, match="sem veredito confirmado"):
        validar(relatorio)


def test_validar_recusa_consulta_inexistente(investigacao):
    pasta, estado = investigacao
    relatorio = montar(estado, pasta, AGORA)
    relatorio["consultas"] = {}
    with pytest.raises(ErroRelatorio, match="inexistentes"):
        validar(relatorio)


def test_html_autocontido_mascarado_e_com_links(investigacao):
    pasta, estado = investigacao
    html = gerar(estado, pasta, AGORA).read_text(encoding="utf-8")
    assert "123.456.789-09" not in html and "***.456.789-**" in html
    assert not re.search(r"<script[^>]+src=|<link[^>]+href=", html)
    assert 'href="#q1"' in html and 'id="q1"' in html
    assert "vegaEmbed" in html and html.count('<svg class="rede"') == 1
    assert "O&#39;Brien" in html or "O'Brien" in html
    relatorio = json.loads((pasta / "relatorio.json").read_text(encoding="utf-8"))
    assert relatorio["id"] == "inv1"


def test_conteudo_externo_e_escapado(investigacao):
    pasta, estado = investigacao
    estado.achados[0].achado.titulo = "ACME <script>alert(1)</script>"
    html = gerar(estado, pasta, AGORA).read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in html


def test_relatorio_vazio_ainda_e_gerado(tmp_path):
    pasta = tmp_path / "inv"
    estado = Estado(id="inv", criada_em=AGORA, situacao="parcial", motivo_parada="orçamento")
    html = gerar(estado, pasta, AGORA).read_text(encoding="utf-8")
    assert "Nenhum achado confirmado" in html


def test_especificacoes_vega_lite():
    tabela = pa.table({"mes": ["2026-01", "2026-02"], "valor": [1.0, 2.0], "orgao": ["A", "B"]})
    for tipo in ("barras", "linha", "dispersao"):
        spec = graficos.especificacao(
            Grafico(tipo=tipo, titulo="t", consulta="q1", x="mes", y="valor"), tabela
        )
        assert spec["data"]["values"][0] == {"mes": "2026-01", "valor": 1.0, "orgao": "A"}
    distribuicao = graficos.especificacao(
        Grafico(tipo="distribuicao", titulo="t", consulta="q1", x="valor"), tabela
    )
    assert distribuicao["encoding"]["x"]["bin"]
    with pytest.raises(ValueError, match="não existem"):
        graficos.especificacao(
            Grafico(tipo="barras", titulo="t", consulta="q1", x="z", y="valor"), tabela
        )


def test_mascarar():
    assert (
        graficos.mascarar("CPF 12345678909 e 111.444.777-35")
        == "CPF ***.456.789-** e ***.444.777-**"
    )
    assert graficos.mascarar("CNPJ 11222333000181") == "CNPJ 11222333000181"


def test_indice(investigacao, tmp_path):
    pasta, estado = investigacao
    from agente import estado as persistencia

    persistencia.salvar(pasta, estado)
    gerar(estado, pasta, AGORA)
    html = gerar_indice(pasta.parent).read_text(encoding="utf-8")
    assert 'href="inv1/relatorio.html"' in html
    assert "Caderno vazio" in html
