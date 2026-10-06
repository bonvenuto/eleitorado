from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from agente import estado as persistencia
from agente.modelos import Achado, Afirmacao, Estado, Grafico, Hipotese, Veredito


def achado(**sobrescritas) -> Achado:
    base = {
        "hipotese_id": "h1",
        "tipo": "situação suspeita",
        "padrao": "fornecedor_sancionado",
        "titulo": "Empresa sancionada recebeu emendas",
        "entidades": {"cnpj_raiz": ["11222333"]},
        "fatos": [{"texto": "R$ 1,2 mi pagos durante a sanção", "consultas": ["q3"]}],
    }
    return Achado.model_validate(base | sobrescritas)


def test_achado_exige_fato_com_consulta():
    with pytest.raises(ValidationError):
        achado(fatos=[])
    with pytest.raises(ValidationError):
        achado(fatos=[{"texto": "R$ 1,2 mi pagos", "consultas": []}])
    with pytest.raises(ValidationError):
        Afirmacao(texto="R$ 1,2 mi pagos", consultas=["tabela_x"])


def test_achado_rejeita_campo_desconhecido_e_padrao_invalido():
    with pytest.raises(ValidationError):
        achado(gravidade="alta")
    with pytest.raises(ValidationError):
        achado(padrao="Fornecedor Sancionado")


def test_consultas_citadas_inclui_graficos():
    a = achado(graficos=[{"tipo": "tabela", "titulo": "Pagamentos", "consulta": "q5"}])
    assert a.consultas_citadas() == {"q3", "q5"}


@pytest.mark.parametrize(
    ("tipo", "campos"),
    [("barras", {"x": "a"}), ("linha", {"y": "b"}), ("rede", {"origem": "a"})],
)
def test_grafico_exige_os_campos_do_tipo(tipo, campos):
    with pytest.raises(ValidationError):
        Grafico(tipo=tipo, titulo="t", consulta="q1", **campos)


def test_veredito_coerente():
    with pytest.raises(ValidationError, match="pendências"):
        Veredito(decisao="inconclusivo", justificativa="faltam dados de 2024")
    with pytest.raises(ValidationError, match="fonte da web"):
        Veredito(
            decisao="confirmado",
            justificativa="confere com o CEIS",
            corroboracao_independente=True,
            alternativas=[{"explicacao": "homônimo", "resultado": "CNPJ idêntico"}],
        )
    with pytest.raises(ValidationError, match="alternativa"):
        Veredito(decisao="confirmado", justificativa="confere com o CEIS")


def test_estado_salva_e_carrega(tmp_path):
    estado = Estado(
        id="20261006-0900-livre",
        criada_em=datetime(2026, 10, 6, 12, tzinfo=UTC),
        hipoteses=[Hipotese(texto="Concentração de emendas", lente="concentração", prioridade=1)],
    )
    persistencia.salvar(tmp_path, estado)
    assert persistencia.carregar(tmp_path) == estado
    assert not (tmp_path / "estado.json.tmp").exists()
    assert persistencia.existe(tmp_path)


def test_busca_hipotese_e_achado_por_id():
    estado = Estado(
        id="x",
        criada_em=datetime(2026, 10, 6, tzinfo=UTC),
        hipoteses=[Hipotese(id="h1", texto="Concentração de emendas", lente="c", prioridade=1)],
    )
    assert estado.hipotese("h1").lente == "c"
    with pytest.raises(KeyError):
        estado.achado("a1")
