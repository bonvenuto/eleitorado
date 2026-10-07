"""Recursos e ZIPs sintéticos do TSE para testes sem rede."""

from coletor.manifesto import Recurso
from tests.amostras import recurso, zip_com


def recurso_tse(id: str) -> Recurso:
    """Recurso anual com famílias explícitas, sem ativar fonte em produção."""
    caminhos = {
        "candidaturas": "consulta_cand/consulta_cand_{ano}.zip",
        "bens": "bem_candidato/bem_candidato_{ano}.zip",
        "contas": "prestacao_contas/prestacao_de_contas_eleitorais_candidatos_{ano}.zip",
    }
    familias = {
        "candidaturas": {"candidaturas": "consulta_cand_{ano}_BRASIL.csv"},
        "bens": {"bens": "bem_candidato_{ano}_BRASIL.csv"},
        "contas": {
            "receitas": "receitas_candidatos_{ano}_BRASIL.csv",
            "contratadas": "despesas_contratadas_candidatos_{ano}_BRASIL.csv",
            "pagamentos": "despesas_pagas_candidatos_{ano}_BRASIL.csv",
            "doador_originario": "receitas_candidatos_doador_originario_{ano}_BRASIL.csv",
        },
    }
    return recurso(
        id=id,
        adaptador="tse_zip",
        fonte_oficial="https://dadosabertos.tse.jus.br/",
        url=f"https://cdn.tse.jus.br/estatistica/sead/odsele/{caminhos[id]}",
        publicacao="por_competencia",
        competencia={"tipo": "ano", "inicio": 2018, "anos": [2018, 2020, 2022, 2024]},
        cadencia={"corrente": "mensal", "anteriores": "mensal"},
        familias=familias[id],
    )


def zip_tse(membros: dict[str, bytes]) -> bytes:
    """Preserva nomes e conteúdo dos membros, inclusive famílias no mesmo ZIP."""
    return zip_com(membros)
