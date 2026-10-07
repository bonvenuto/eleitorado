"""`coletor site`: contrato (esquemas × exemplos) e gravação dos arquivos do site."""

import json

import pytest

from coletor.site import TIPOS, carregar_validadores, tipo_do_caminho
from tests.amostras import RAIZ

ESQUEMAS = RAIZ / "site" / "esquemas"
EXEMPLOS = RAIZ / "site" / "exemplos"


def _exemplos() -> dict[str, dict]:
    return {
        p.relative_to(EXEMPLOS).as_posix(): json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(EXEMPLOS.rglob("*.json"))
    }


# ---- contrato: exemplos × esquemas


@pytest.mark.parametrize("caminho", sorted(_exemplos()))
def test_exemplo_segue_o_esquema(caminho):
    validadores = carregar_validadores(ESQUEMAS)
    documento = _exemplos()[caminho]
    erros = [e.message for e in validadores[tipo_do_caminho(caminho)].iter_errors(documento)]
    assert erros == []


def test_todo_tipo_de_arquivo_tem_exemplo():
    assert {tipo_do_caminho(c) for c in _exemplos()} == set(TIPOS)


def test_esquema_recusa_campo_que_nao_existe():
    validadores = carregar_validadores(ESQUEMAS)
    documento = _exemplos()["parlamentar/camara-900001.json"]
    documento["cota"]["inventado"] = 1
    assert list(validadores["parlamentar"].iter_errors(documento))


def test_esquema_aceita_cnpj_alfanumerico():
    validadores = carregar_validadores(ESQUEMAS)
    documento = _exemplos()["empresa/b_112.json"]
    documento["bloco"] = "1AB"
    documento["empresas"] = {"1AB2C3D4": documento["empresas"]["11222333"]}
    assert list(validadores["empresa"].iter_errors(documento)) == []
