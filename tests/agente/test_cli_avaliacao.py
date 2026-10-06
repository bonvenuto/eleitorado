import json
from datetime import UTC, datetime

import duckdb

from agente import cli
from agente.avaliacao import (
    ACME,
    ALFA_COTA,
    DELTA,
    _digitos_cnpj,
    contexto_de_avaliacao,
    criar_lago,
    preparar_avaliacao,
    verificar,
)
from agente.config import carregar
from agente.modelos import Achado, Estado, RegistroAchado

AGORA = datetime(2026, 10, 6, tzinfo=UTC)


def registro(
    situacao: str,
    cnpj_raiz: str,
    titulo: str = "Pagamentos durante a sanção",
    tipo: str = "situação suspeita",
):
    achado = Achado(
        hipotese_id="h1",
        tipo=tipo,
        padrao="p",
        titulo=titulo,
        entidades={"cnpj_raiz": [cnpj_raiz]},
        fatos=[{"texto": "pagamentos na vigência", "consultas": ["q1"]}],
    )
    return RegistroAchado(id="a1", achado=achado, situacao=situacao)


def test_lago_de_avaliacao_tem_os_casos_plantados(tmp_path):
    criar_lago(tmp_path)
    conexao = duckdb.connect(str(tmp_path / "agente.duckdb"), read_only=True)
    alertas = conexao.sql(
        "select favorecido_nome, count(*) from marts.alerta_emenda_favorecido_sancionado group by 1"
    ).fetchall()
    assert alertas == [(ACME[1], 6)]
    maior = conexao.sql(
        "select fornecedor_nome from marts.fct_despesa_cota_parlamentar "
        "order by valor_reembolsado desc limit 1"
    ).fetchone()
    assert maior == (DELTA[1],)
    genericos = conexao.sql(
        "select count(*) from marts.fct_despesa_cota_parlamentar "
        "where regexp_matches(fornecedor_nome, 'FORNECEDOR')"
    ).fetchone()
    assert genericos == (0,)  # nomes plausíveis: o agente não deve tomar a base por teste
    homonimos = conexao.sql(
        "select count(*) from marts.dim_parlamentar where nome = 'JOSE DA SILVA'"
    ).fetchone()
    assert homonimos == (2,)
    conexao.close()


def test_verificar():
    estado = Estado(
        id="x",
        criada_em=AGORA,
        achados=[
            registro("confirmado", ACME[0][:8]),
            registro("inconclusivo", DELTA[0][:8], "Despesa muito acima do normal"),
        ],
    )
    assert all(verificar(estado).values())
    homonimo = registro(
        "confirmado", ALFA_COTA[0][:8], "Homônimos com CNPJ diferente", "qualidade de dado"
    )
    estado.achados.append(homonimo)
    assert all(verificar(estado).values())  # apontar o homônimo como qualidade de dado é o certo
    estado.achados.append(registro("confirmado", ALFA_COTA[0][:8]))
    assert not verificar(estado)["armadilha de homônimo não confirmada"]
    assert not verificar(Estado(id="y", criada_em=AGORA))["caso sancionado confirmado"]


def test_preparar_avaliacao_isola_lago_e_investigacoes(tmp_path):
    arquivo = preparar_avaliacao(tmp_path, "haiku")
    config = carregar(arquivo, tmp_path)
    assert config.lago == (tmp_path / "avaliacao" / "lago").resolve()
    assert config.investigacoes == (tmp_path / "avaliacao" / "investigacoes").resolve()
    assert config.modelo == "haiku" and config.banco.exists()
    preparar_avaliacao(tmp_path, None)  # recria do zero
    assert carregar(arquivo, tmp_path).modelo is None


def test_caderno_vazio_e_trava(monkeypatch, tmp_path, capsys):
    config = carregar(raiz=tmp_path)
    monkeypatch.setattr(cli, "carregar", lambda *a, **k: config)
    assert cli.main(["caderno"]) == 0
    config.investigacoes.mkdir(parents=True)
    trava = config.investigacoes / ".trava"
    trava.write_text(json.dumps({"pid": 1, "desde": datetime.now(UTC).isoformat()}), "utf-8")
    assert cli.main(["investigar"]) == cli.SAIDA_TRAVA
    assert "em andamento" in capsys.readouterr().err


def test_cnpjs_com_digitos_verificadores_validos_e_aviso():
    assert _digitos_cnpj("11222333") == "11222333000181"  # exemplo conhecido e válido
    assert ACME[0] == _digitos_cnpj(ACME[0][:8])
    texto = contexto_de_avaliacao("# Contexto dos dados")
    assert texto.startswith("## Aviso: ambiente de avaliação")
    assert texto.endswith("# Contexto dos dados")
