from datetime import date

import httpx

from coletor.adaptadores import api_detalhe
from coletor.competencias import Competencia
from tests.amostras import json_bytes, pagina_deputados, recurso

HOJE = date(2026, 10, 6)
LISTA = "https://dadosabertos.camara.leg.br/api/v2/deputados"


def _recurso():
    return recurso(
        id="deputados_detalhe",
        adaptador="api_detalhe",
        url=LISTA,
        url_detalhe=f"{LISTA}/{{id}}",
        parametros={"itens": 100},
        competencia={"tipo": "data_coleta"},
        cadencia={"corrente": "mensal"},
        formato={"tipo": "json"},
        paginacao="links_next",
        iteracao={"parametro": "idLegislatura", "valores": "legislaturas", "inicio": 57},
        registros="dados",
    )


def test_busca_o_detalhe_de_cada_id_da_lista_sem_repetir(respx_mock, http, tmp_path):
    # o mesmo deputado aparece em duas páginas: o detalhe é buscado uma vez só
    respx_mock.get(LISTA, params={"idLegislatura": 57}).mock(
        return_value=httpx.Response(200, content=json_bytes(pagina_deputados([7, 9, 7], None)))
    )
    for id_ in (7, 9):
        respx_mock.get(f"{LISTA}/{id_}").mock(
            return_value=httpx.Response(
                200, content=json_bytes({"dados": {"id": id_, "nomeCivil": f"N{id_}"}})
            )
        )
    competencia = Competencia.de_dia(HOJE)
    extracao = api_detalhe.extrair(_recurso(), competencia, tmp_path, http, HOJE)
    preparado = api_detalhe.preparar(_recurso(), competencia, extracao.arquivo_original, tmp_path)
    assert preparado.registros == [{"id": 7, "nomeCivil": "N7"}, {"id": 9, "nomeCivil": "N9"}]
    assert extracao.parametros["ids"] == 2
    assert extracao.extensao == "jsonl.gz"
