"""Amostras reduzidas das fontes, com documentos e nomes fictícios."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from coletor.manifesto import Recurso

RAIZ = Path(__file__).resolve().parents[1]

# 07:30 em Brasília (UTC-3) de 03/10/2026
AGORA = datetime(2026, 10, 3, 10, 30, tzinfo=UTC)

CEAP_CSV = (
    '"txNomeParlamentar";"cpf";"ideCadastro";"txtDescricao";"txtCNPJCPF";"vlrLiquido";"numAno"\n'
    '"DEPUTADO EXEMPLO";"00000000191";"1001";"LOCOMOÇÃO, ALIMENTAÇÃO E  HOSPEDAGEM";'
    '"11.222.333/0001-81";"3800";"2008"\n'
    '"LIDERANÇA DO PARTIDO";"";"";"TELEFONIA";"11.222.333/0001-81";"104.67";"2008"\n'
)

CNEP_CSV = (
    '"CADASTRO";"CÓDIGO DA SANÇÃO";"TIPO DE PESSOA";"CPF OU CNPJ DO SANCIONADO";'
    '"NOME DO SANCIONADO";"ABRAGÊNCIA DA SANÇÃO";"OBSERVAÇÕES"\n'
    '"CNEP";"1";"J";"11222333000181";"Empresa Exemplo Comércio Ltda";'
    '"Todas as Esferas em todos os Poderes";"linha 1\nlinha 2"\n'
    '"CNEP";"2";"F";"00000000191";"Pessoa Exemplo";"No órgão sancionador";""\n'
)

PAGINA_CGU = (
    "<html><script>var arquivos = [];\n"
    'arquivos.push({"ano" : "2026", "mes" : "10", "dia" : "02", "origem" :  "CEIS"});\n'
    "</script></html>"
)

CEAPS_JSON: list[dict[str, Any]] = [
    {
        "id": 2008080011403,
        "ano": 2008,
        "mes": 8,
        "codSenador": 3,
        "nomeSenador": "SENADOR EXEMPLO",
        "tipoDespesa": "Locomoção, hospedagem, alimentação, combustíveis e lubrificantes",
        "cpfCnpj": None,
        "fornecedor": None,
        "valorReembolsado": 386.6,
    },
    {
        "id": 2269008,
        "ano": 2008,
        "mes": 9,
        "codSenador": 3,
        "nomeSenador": "SENADOR EXEMPLO",
        "tipoDespesa": "Contratação de consultorias",
        "cpfCnpj": "11.222.333/0001-81",
        "fornecedor": "EMPRESA EXEMPLO",
        "valorReembolsado": 500,
    },
]


def senadores_json(versao: str) -> dict[str, Any]:
    return {
        "ListaParlamentarLegislatura": {
            "Metadados": {"Versao": versao},
            "Parlamentares": {
                "Parlamentar": [
                    {
                        "IdentificacaoParlamentar": {
                            "CodigoParlamentar": "3",
                            "NomeParlamentar": "A",
                        }
                    },
                    {
                        "IdentificacaoParlamentar": {
                            "CodigoParlamentar": "9",
                            "NomeParlamentar": "B",
                        }
                    },
                ]
            },
        }
    }


def pagina_deputados(ids: list[int], proxima: str | None) -> dict[str, Any]:
    links = [{"rel": "self", "href": "https://exemplo/self"}]
    if proxima:
        links.append({"rel": "next", "href": proxima})
    return {"dados": [{"id": i, "nome": f"Deputado {i}"} for i in ids], "links": links}


def zip_com(
    membros: dict[str, bytes], data_hora: tuple[int, ...] = (2026, 10, 2, 18, 0, 0)
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as arquivo:
        for nome, conteudo in membros.items():
            info = zipfile.ZipInfo(nome, date_time=data_hora)
            arquivo.writestr(info, conteudo)
    return buffer.getvalue()


def json_bytes(dados: Any) -> bytes:
    return json.dumps(dados, ensure_ascii=False).encode("utf-8")


def recurso(**sobrescritas: Any) -> Recurso:
    """Recurso válido de teste; `sobrescritas` troca campos de primeiro nível."""
    base: dict[str, Any] = {
        "id": "cnep",
        "descricao": "teste",
        "fonte_oficial": "https://exemplo",
        "condicoes_uso": "teste",
        "adaptador": "arquivo",
        "url": "https://portaldatransparencia.gov.br/download-de-dados/cnep/{data}",
        "publicacao": "snapshot",
        "competencia": {
            "tipo": "data_arquivo",
            "pagina": "https://portaldatransparencia.gov.br/download-de-dados/cnep",
        },
        "cadencia": {"corrente": "diaria"},
        "formato": {"tipo": "csv", "compressao": "zip", "encoding": "cp1252"},
    }
    base.update(sobrescritas)
    return Recurso.model_validate(base)
