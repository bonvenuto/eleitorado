"""ZIPs TSE sintéticos: seleção, layouts e integridade sem rede."""

import io
import zipfile
from datetime import date

import httpx
import pytest
import respx

from coletor.adaptadores.base import ErroColeta
from coletor.adaptadores.tse_zip import extrair, preparar_familias
from coletor.competencias import Competencia
from coletor.http import ClienteHttp
from tests.amostras_tse import recurso_tse, zip_tse

# Somente cabeçalhos públicos conferidos no protótipo; nenhum registro real.
CABECALHOS = {
    (2018, "bem_candidato_2018_BRASIL.csv"): (
        "DT_GERACAO",
        "HH_GERACAO",
        "ANO_ELEICAO",
        "CD_TIPO_ELEICAO",
        "NM_TIPO_ELEICAO",
        "CD_ELEICAO",
        "DS_ELEICAO",
        "DT_ELEICAO",
        "SG_UF",
        "SG_UE",
        "NM_UE",
        "SQ_CANDIDATO",
        "NR_ORDEM_BEM_CANDIDATO",
        "CD_TIPO_BEM_CANDIDATO",
        "DS_TIPO_BEM_CANDIDATO",
        "DS_BEM_CANDIDATO",
        "VR_BEM_CANDIDATO",
        "DT_ULT_ATUAL_BEM_CANDIDATO",
        "HH_ULT_ATUAL_BEM_CANDIDATO",
    ),
    (2018, "consulta_cand_2018_BRASIL.csv"): (
        "DT_GERACAO",
        "HH_GERACAO",
        "ANO_ELEICAO",
        "CD_TIPO_ELEICAO",
        "NM_TIPO_ELEICAO",
        "NR_TURNO",
        "CD_ELEICAO",
        "DS_ELEICAO",
        "DT_ELEICAO",
        "TP_ABRANGENCIA",
        "SG_UF",
        "SG_UE",
        "NM_UE",
        "CD_CARGO",
        "DS_CARGO",
        "SQ_CANDIDATO",
        "NR_CANDIDATO",
        "NM_CANDIDATO",
        "NM_URNA_CANDIDATO",
        "NM_SOCIAL_CANDIDATO",
        "NR_CPF_CANDIDATO",
        "DS_EMAIL",
        "CD_SITUACAO_CANDIDATURA",
        "DS_SITUACAO_CANDIDATURA",
        "TP_AGREMIACAO",
        "NR_PARTIDO",
        "SG_PARTIDO",
        "NM_PARTIDO",
        "NR_FEDERACAO",
        "NM_FEDERACAO",
        "SG_FEDERACAO",
        "DS_COMPOSICAO_FEDERACAO",
        "SQ_COLIGACAO",
        "NM_COLIGACAO",
        "DS_COMPOSICAO_COLIGACAO",
        "SG_UF_NASCIMENTO",
        "DT_NASCIMENTO",
        "NR_TITULO_ELEITORAL_CANDIDATO",
        "CD_GENERO",
        "DS_GENERO",
        "CD_GRAU_INSTRUCAO",
        "DS_GRAU_INSTRUCAO",
        "CD_ESTADO_CIVIL",
        "DS_ESTADO_CIVIL",
        "CD_COR_RACA",
        "DS_COR_RACA",
        "CD_OCUPACAO",
        "DS_OCUPACAO",
        "CD_SIT_TOT_TURNO",
        "DS_SIT_TOT_TURNO",
    ),
    (2018, "despesas_contratadas_candidatos_2018_BRASIL.csv"): (
        "DT_GERACAO",
        "HH_GERACAO",
        "AA_ELEICAO",
        "CD_TIPO_ELEICAO",
        "NM_TIPO_ELEICAO",
        "CD_ELEICAO",
        "DS_ELEICAO",
        "DT_ELEICAO",
        "ST_TURNO",
        "TP_PRESTACAO_CONTAS",
        "DT_PRESTACAO_CONTAS",
        "SQ_PRESTADOR_CONTAS",
        "SG_UF",
        "SG_UE",
        "NM_UE",
        "NR_CNPJ_PRESTADOR_CONTA",
        "CD_CARGO",
        "DS_CARGO",
        "SQ_CANDIDATO",
        "NR_CANDIDATO",
        "NM_CANDIDATO",
        "NR_CPF_CANDIDATO",
        "NR_CPF_VICE_CANDIDATO",
        "NR_PARTIDO",
        "SG_PARTIDO",
        "NM_PARTIDO",
        "CD_TIPO_FORNECEDOR",
        "DS_TIPO_FORNECEDOR",
        "CD_CNAE_FORNECEDOR",
        "DS_CNAE_FORNECEDOR",
        "NR_CPF_CNPJ_FORNECEDOR",
        "NM_FORNECEDOR",
        "NM_FORNECEDOR_RFB",
        "CD_ESFERA_PART_FORNECEDOR",
        "DS_ESFERA_PART_FORNECEDOR",
        "SG_UF_FORNECEDOR",
        "CD_MUNICIPIO_FORNECEDOR",
        "NM_MUNICIPIO_FORNECEDOR",
        "SQ_CANDIDATO_FORNECEDOR",
        "NR_CANDIDATO_FORNECEDOR",
        "CD_CARGO_FORNECEDOR",
        "DS_CARGO_FORNECEDOR",
        "NR_PARTIDO_FORNECEDOR",
        "SG_PARTIDO_FORNECEDOR",
        "NM_PARTIDO_FORNECEDOR",
        "DS_TIPO_DOCUMENTO",
        "NR_DOCUMENTO",
        "CD_ORIGEM_DESPESA",
        "DS_ORIGEM_DESPESA",
        "SQ_DESPESA",
        "DT_DESPESA",
        "DS_DESPESA",
        "VR_DESPESA_CONTRATADA",
    ),
    (2018, "despesas_pagas_candidatos_2018_BRASIL.csv"): (
        "DT_GERACAO",
        "HH_GERACAO",
        "AA_ELEICAO",
        "CD_TIPO_ELEICAO",
        "NM_TIPO_ELEICAO",
        "CD_ELEICAO",
        "DS_ELEICAO",
        "DT_ELEICAO",
        "ST_TURNO",
        "TP_PRESTACAO_CONTAS",
        "DT_PRESTACAO_CONTAS",
        "SQ_PRESTADOR_CONTAS",
        "SG_UF",
        "DS_TIPO_DOCUMENTO",
        "NR_DOCUMENTO",
        "CD_FONTE_DESPESA",
        "DS_FONTE_DESPESA",
        "CD_ORIGEM_DESPESA",
        "DS_ORIGEM_DESPESA",
        "CD_NATUREZA_DESPESA",
        "DS_NATUREZA_DESPESA",
        "CD_ESPECIE_RECURSO",
        "DS_ESPECIE_RECURSO",
        "SQ_DESPESA",
        "SQ_PARCELAMENTO_DESPESA",
        "DT_PAGTO_DESPESA",
        "DS_DESPESA",
        "VR_PAGTO_DESPESA",
    ),
    (2018, "receitas_candidatos_2018_BRASIL.csv"): (
        "DT_GERACAO",
        "HH_GERACAO",
        "AA_ELEICAO",
        "CD_TIPO_ELEICAO",
        "NM_TIPO_ELEICAO",
        "CD_ELEICAO",
        "DS_ELEICAO",
        "DT_ELEICAO",
        "ST_TURNO",
        "TP_PRESTACAO_CONTAS",
        "DT_PRESTACAO_CONTAS",
        "SQ_PRESTADOR_CONTAS",
        "SG_UF",
        "SG_UE",
        "NM_UE",
        "NR_CNPJ_PRESTADOR_CONTA",
        "CD_CARGO",
        "DS_CARGO",
        "SQ_CANDIDATO",
        "NR_CANDIDATO",
        "NM_CANDIDATO",
        "NR_CPF_CANDIDATO",
        "NR_CPF_VICE_CANDIDATO",
        "NR_PARTIDO",
        "SG_PARTIDO",
        "NM_PARTIDO",
        "CD_FONTE_RECEITA",
        "DS_FONTE_RECEITA",
        "CD_ORIGEM_RECEITA",
        "DS_ORIGEM_RECEITA",
        "CD_NATUREZA_RECEITA",
        "DS_NATUREZA_RECEITA",
        "CD_ESPECIE_RECEITA",
        "DS_ESPECIE_RECEITA",
        "CD_CNAE_DOADOR",
        "DS_CNAE_DOADOR",
        "NR_CPF_CNPJ_DOADOR",
        "NM_DOADOR",
        "NM_DOADOR_RFB",
        "CD_ESFERA_PARTIDARIA_DOADOR",
        "DS_ESFERA_PARTIDARIA_DOADOR",
        "SG_UF_DOADOR",
        "CD_MUNICIPIO_DOADOR",
        "NM_MUNICIPIO_DOADOR",
        "SQ_CANDIDATO_DOADOR",
        "NR_CANDIDATO_DOADOR",
        "CD_CARGO_CANDIDATO_DOADOR",
        "DS_CARGO_CANDIDATO_DOADOR",
        "NR_PARTIDO_DOADOR",
        "SG_PARTIDO_DOADOR",
        "NM_PARTIDO_DOADOR",
        "NR_RECIBO_DOACAO",
        "NR_DOCUMENTO_DOACAO",
        "SQ_RECEITA",
        "DT_RECEITA",
        "DS_RECEITA",
        "VR_RECEITA",
        "DS_NATUREZA_RECURSO_ESTIMAVEL",
        "DS_GENERO",
        "DS_COR_RACA",
    ),
    (2018, "receitas_candidatos_doador_originario_2018_BRASIL.csv"): (
        "DT_GERACAO",
        "HH_GERACAO",
        "AA_ELEICAO",
        "CD_TIPO_ELEICAO",
        "NM_TIPO_ELEICAO",
        "CD_ELEICAO",
        "DS_ELEICAO",
        "DT_ELEICAO",
        "ST_TURNO",
        "TP_PRESTACAO_CONTAS",
        "DT_PRESTACAO_CONTAS",
        "SQ_PRESTADOR_CONTAS",
        "SG_UF",
        "NR_CPF_CNPJ_DOADOR_ORIGINARIO",
        "NM_DOADOR_ORIGINARIO",
        "NM_DOADOR_ORIGINARIO_RFB",
        "TP_DOADOR_ORIGINARIO",
        "CD_CNAE_DOADOR_ORIGINARIO",
        "DS_CNAE_DOADOR_ORIGINARIO",
        "SQ_RECEITA",
        "DT_RECEITA",
        "DS_RECEITA",
        "VR_RECEITA",
    ),
    (2020, "bem_candidato_2020_BRASIL.csv"): (
        "DT_GERACAO",
        "HH_GERACAO",
        "ANO_ELEICAO",
        "CD_TIPO_ELEICAO",
        "NM_TIPO_ELEICAO",
        "CD_ELEICAO",
        "DS_ELEICAO",
        "DT_ELEICAO",
        "SG_UF",
        "SG_UE",
        "NM_UE",
        "SQ_CANDIDATO",
        "NR_ORDEM_BEM_CANDIDATO",
        "CD_TIPO_BEM_CANDIDATO",
        "DS_TIPO_BEM_CANDIDATO",
        "DS_BEM_CANDIDATO",
        "VR_BEM_CANDIDATO",
        "DT_ULT_ATUAL_BEM_CANDIDATO",
        "HH_ULT_ATUAL_BEM_CANDIDATO",
    ),
    (2020, "consulta_cand_2020_BRASIL.csv"): (
        "DT_GERACAO",
        "HH_GERACAO",
        "ANO_ELEICAO",
        "CD_TIPO_ELEICAO",
        "NM_TIPO_ELEICAO",
        "NR_TURNO",
        "CD_ELEICAO",
        "DS_ELEICAO",
        "DT_ELEICAO",
        "TP_ABRANGENCIA",
        "SG_UF",
        "SG_UE",
        "NM_UE",
        "CD_CARGO",
        "DS_CARGO",
        "SQ_CANDIDATO",
        "NR_CANDIDATO",
        "NM_CANDIDATO",
        "NM_URNA_CANDIDATO",
        "NM_SOCIAL_CANDIDATO",
        "NR_CPF_CANDIDATO",
        "DS_EMAIL",
        "CD_SITUACAO_CANDIDATURA",
        "DS_SITUACAO_CANDIDATURA",
        "TP_AGREMIACAO",
        "NR_PARTIDO",
        "SG_PARTIDO",
        "NM_PARTIDO",
        "NR_FEDERACAO",
        "NM_FEDERACAO",
        "SG_FEDERACAO",
        "DS_COMPOSICAO_FEDERACAO",
        "SQ_COLIGACAO",
        "NM_COLIGACAO",
        "DS_COMPOSICAO_COLIGACAO",
        "SG_UF_NASCIMENTO",
        "DT_NASCIMENTO",
        "NR_TITULO_ELEITORAL_CANDIDATO",
        "CD_GENERO",
        "DS_GENERO",
        "CD_GRAU_INSTRUCAO",
        "DS_GRAU_INSTRUCAO",
        "CD_ESTADO_CIVIL",
        "DS_ESTADO_CIVIL",
        "CD_COR_RACA",
        "DS_COR_RACA",
        "CD_OCUPACAO",
        "DS_OCUPACAO",
        "CD_SIT_TOT_TURNO",
        "DS_SIT_TOT_TURNO",
    ),
    (2020, "despesas_contratadas_candidatos_2020_BRASIL.csv"): (
        "DT_GERACAO",
        "HH_GERACAO",
        "AA_ELEICAO",
        "CD_TIPO_ELEICAO",
        "NM_TIPO_ELEICAO",
        "CD_ELEICAO",
        "DS_ELEICAO",
        "DT_ELEICAO",
        "ST_TURNO",
        "TP_PRESTACAO_CONTAS",
        "DT_PRESTACAO_CONTAS",
        "SQ_PRESTADOR_CONTAS",
        "SG_UF",
        "SG_UE",
        "NM_UE",
        "NR_CNPJ_PRESTADOR_CONTA",
        "CD_CARGO",
        "DS_CARGO",
        "SQ_CANDIDATO",
        "NR_CANDIDATO",
        "NM_CANDIDATO",
        "NR_CPF_CANDIDATO",
        "NR_CPF_VICE_CANDIDATO",
        "NR_PARTIDO",
        "SG_PARTIDO",
        "NM_PARTIDO",
        "CD_TIPO_FORNECEDOR",
        "DS_TIPO_FORNECEDOR",
        "CD_CNAE_FORNECEDOR",
        "DS_CNAE_FORNECEDOR",
        "NR_CPF_CNPJ_FORNECEDOR",
        "NM_FORNECEDOR",
        "NM_FORNECEDOR_RFB",
        "CD_ESFERA_PART_FORNECEDOR",
        "DS_ESFERA_PART_FORNECEDOR",
        "SG_UF_FORNECEDOR",
        "CD_MUNICIPIO_FORNECEDOR",
        "NM_MUNICIPIO_FORNECEDOR",
        "SQ_CANDIDATO_FORNECEDOR",
        "NR_CANDIDATO_FORNECEDOR",
        "CD_CARGO_FORNECEDOR",
        "DS_CARGO_FORNECEDOR",
        "NR_PARTIDO_FORNECEDOR",
        "SG_PARTIDO_FORNECEDOR",
        "NM_PARTIDO_FORNECEDOR",
        "DS_TIPO_DOCUMENTO",
        "NR_DOCUMENTO",
        "CD_ORIGEM_DESPESA",
        "DS_ORIGEM_DESPESA",
        "SQ_DESPESA",
        "DT_DESPESA",
        "DS_DESPESA",
        "VR_DESPESA_CONTRATADA",
    ),
    (2020, "despesas_pagas_candidatos_2020_BRASIL.csv"): (
        "DT_GERACAO",
        "HH_GERACAO",
        "AA_ELEICAO",
        "CD_TIPO_ELEICAO",
        "NM_TIPO_ELEICAO",
        "CD_ELEICAO",
        "DS_ELEICAO",
        "DT_ELEICAO",
        "ST_TURNO",
        "TP_PRESTACAO_CONTAS",
        "DT_PRESTACAO_CONTAS",
        "SQ_PRESTADOR_CONTAS",
        "SG_UF",
        "DS_TIPO_DOCUMENTO",
        "NR_DOCUMENTO",
        "CD_FONTE_DESPESA",
        "DS_FONTE_DESPESA",
        "CD_ORIGEM_DESPESA",
        "DS_ORIGEM_DESPESA",
        "CD_NATUREZA_DESPESA",
        "DS_NATUREZA_DESPESA",
        "CD_ESPECIE_RECURSO",
        "DS_ESPECIE_RECURSO",
        "SQ_DESPESA",
        "SQ_PARCELAMENTO_DESPESA",
        "DT_PAGTO_DESPESA",
        "DS_DESPESA",
        "VR_PAGTO_DESPESA",
    ),
    (2020, "receitas_candidatos_2020_BRASIL.csv"): (
        "DT_GERACAO",
        "HH_GERACAO",
        "AA_ELEICAO",
        "CD_TIPO_ELEICAO",
        "NM_TIPO_ELEICAO",
        "CD_ELEICAO",
        "DS_ELEICAO",
        "DT_ELEICAO",
        "ST_TURNO",
        "TP_PRESTACAO_CONTAS",
        "DT_PRESTACAO_CONTAS",
        "SQ_PRESTADOR_CONTAS",
        "SG_UF",
        "SG_UE",
        "NM_UE",
        "NR_CNPJ_PRESTADOR_CONTA",
        "CD_CARGO",
        "DS_CARGO",
        "SQ_CANDIDATO",
        "NR_CANDIDATO",
        "NM_CANDIDATO",
        "NR_CPF_CANDIDATO",
        "NR_CPF_VICE_CANDIDATO",
        "NR_PARTIDO",
        "SG_PARTIDO",
        "NM_PARTIDO",
        "CD_FONTE_RECEITA",
        "DS_FONTE_RECEITA",
        "CD_ORIGEM_RECEITA",
        "DS_ORIGEM_RECEITA",
        "CD_NATUREZA_RECEITA",
        "DS_NATUREZA_RECEITA",
        "CD_ESPECIE_RECEITA",
        "DS_ESPECIE_RECEITA",
        "CD_CNAE_DOADOR",
        "DS_CNAE_DOADOR",
        "NR_CPF_CNPJ_DOADOR",
        "NM_DOADOR",
        "NM_DOADOR_RFB",
        "CD_ESFERA_PARTIDARIA_DOADOR",
        "DS_ESFERA_PARTIDARIA_DOADOR",
        "SG_UF_DOADOR",
        "CD_MUNICIPIO_DOADOR",
        "NM_MUNICIPIO_DOADOR",
        "SQ_CANDIDATO_DOADOR",
        "NR_CANDIDATO_DOADOR",
        "CD_CARGO_CANDIDATO_DOADOR",
        "DS_CARGO_CANDIDATO_DOADOR",
        "NR_PARTIDO_DOADOR",
        "SG_PARTIDO_DOADOR",
        "NM_PARTIDO_DOADOR",
        "NR_RECIBO_DOACAO",
        "NR_DOCUMENTO_DOACAO",
        "SQ_RECEITA",
        "DT_RECEITA",
        "DS_RECEITA",
        "VR_RECEITA",
        "DS_NATUREZA_RECURSO_ESTIMAVEL",
        "DS_GENERO",
        "DS_COR_RACA",
    ),
    (2020, "receitas_candidatos_doador_originario_2020_BRASIL.csv"): (
        "DT_GERACAO",
        "HH_GERACAO",
        "AA_ELEICAO",
        "CD_TIPO_ELEICAO",
        "NM_TIPO_ELEICAO",
        "CD_ELEICAO",
        "DS_ELEICAO",
        "DT_ELEICAO",
        "ST_TURNO",
        "TP_PRESTACAO_CONTAS",
        "DT_PRESTACAO_CONTAS",
        "SQ_PRESTADOR_CONTAS",
        "SG_UF",
        "NR_CPF_CNPJ_DOADOR_ORIGINARIO",
        "NM_DOADOR_ORIGINARIO",
        "NM_DOADOR_ORIGINARIO_RFB",
        "TP_DOADOR_ORIGINARIO",
        "CD_CNAE_DOADOR_ORIGINARIO",
        "DS_CNAE_DOADOR_ORIGINARIO",
        "SQ_RECEITA",
        "DT_RECEITA",
        "DS_RECEITA",
        "VR_RECEITA",
    ),
    (2022, "bem_candidato_2022_BRASIL.csv"): (
        "DT_GERACAO",
        "HH_GERACAO",
        "ANO_ELEICAO",
        "CD_TIPO_ELEICAO",
        "NM_TIPO_ELEICAO",
        "CD_ELEICAO",
        "DS_ELEICAO",
        "DT_ELEICAO",
        "SG_UF",
        "SG_UE",
        "NM_UE",
        "SQ_CANDIDATO",
        "NR_ORDEM_BEM_CANDIDATO",
        "CD_TIPO_BEM_CANDIDATO",
        "DS_TIPO_BEM_CANDIDATO",
        "DS_BEM_CANDIDATO",
        "VR_BEM_CANDIDATO",
        "DT_ULT_ATUAL_BEM_CANDIDATO",
        "HH_ULT_ATUAL_BEM_CANDIDATO",
    ),
    (2022, "consulta_cand_2022_BRASIL.csv"): (
        "DT_GERACAO",
        "HH_GERACAO",
        "ANO_ELEICAO",
        "CD_TIPO_ELEICAO",
        "NM_TIPO_ELEICAO",
        "NR_TURNO",
        "CD_ELEICAO",
        "DS_ELEICAO",
        "DT_ELEICAO",
        "TP_ABRANGENCIA",
        "SG_UF",
        "SG_UE",
        "NM_UE",
        "CD_CARGO",
        "DS_CARGO",
        "SQ_CANDIDATO",
        "NR_CANDIDATO",
        "NM_CANDIDATO",
        "NM_URNA_CANDIDATO",
        "NM_SOCIAL_CANDIDATO",
        "NR_CPF_CANDIDATO",
        "DS_EMAIL",
        "CD_SITUACAO_CANDIDATURA",
        "DS_SITUACAO_CANDIDATURA",
        "TP_AGREMIACAO",
        "NR_PARTIDO",
        "SG_PARTIDO",
        "NM_PARTIDO",
        "NR_FEDERACAO",
        "NM_FEDERACAO",
        "SG_FEDERACAO",
        "DS_COMPOSICAO_FEDERACAO",
        "SQ_COLIGACAO",
        "NM_COLIGACAO",
        "DS_COMPOSICAO_COLIGACAO",
        "SG_UF_NASCIMENTO",
        "DT_NASCIMENTO",
        "NR_TITULO_ELEITORAL_CANDIDATO",
        "CD_GENERO",
        "DS_GENERO",
        "CD_GRAU_INSTRUCAO",
        "DS_GRAU_INSTRUCAO",
        "CD_ESTADO_CIVIL",
        "DS_ESTADO_CIVIL",
        "CD_COR_RACA",
        "DS_COR_RACA",
        "CD_OCUPACAO",
        "DS_OCUPACAO",
        "CD_SIT_TOT_TURNO",
        "DS_SIT_TOT_TURNO",
    ),
    (2022, "despesas_contratadas_candidatos_2022_BRASIL.csv"): (
        "DT_GERACAO",
        "HH_GERACAO",
        "AA_ELEICAO",
        "CD_TIPO_ELEICAO",
        "NM_TIPO_ELEICAO",
        "CD_ELEICAO",
        "DS_ELEICAO",
        "DT_ELEICAO",
        "ST_TURNO",
        "TP_PRESTACAO_CONTAS",
        "DT_PRESTACAO_CONTAS",
        "SQ_PRESTADOR_CONTAS",
        "SG_UF",
        "SG_UE",
        "NM_UE",
        "NR_CNPJ_PRESTADOR_CONTA",
        "CD_CARGO",
        "DS_CARGO",
        "SQ_CANDIDATO",
        "NR_CANDIDATO",
        "NM_CANDIDATO",
        "NR_CPF_CANDIDATO",
        "NR_CPF_VICE_CANDIDATO",
        "NR_PARTIDO",
        "SG_PARTIDO",
        "NM_PARTIDO",
        "CD_TIPO_FORNECEDOR",
        "DS_TIPO_FORNECEDOR",
        "CD_CNAE_FORNECEDOR",
        "DS_CNAE_FORNECEDOR",
        "NR_CPF_CNPJ_FORNECEDOR",
        "NM_FORNECEDOR",
        "NM_FORNECEDOR_RFB",
        "CD_ESFERA_PART_FORNECEDOR",
        "DS_ESFERA_PART_FORNECEDOR",
        "SG_UF_FORNECEDOR",
        "CD_MUNICIPIO_FORNECEDOR",
        "NM_MUNICIPIO_FORNECEDOR",
        "SQ_CANDIDATO_FORNECEDOR",
        "NR_CANDIDATO_FORNECEDOR",
        "CD_CARGO_FORNECEDOR",
        "DS_CARGO_FORNECEDOR",
        "NR_PARTIDO_FORNECEDOR",
        "SG_PARTIDO_FORNECEDOR",
        "NM_PARTIDO_FORNECEDOR",
        "DS_TIPO_DOCUMENTO",
        "NR_DOCUMENTO",
        "CD_ORIGEM_DESPESA",
        "DS_ORIGEM_DESPESA",
        "SQ_DESPESA",
        "DT_DESPESA",
        "DS_DESPESA",
        "VR_DESPESA_CONTRATADA",
    ),
    (2022, "despesas_pagas_candidatos_2022_BRASIL.csv"): (
        "DT_GERACAO",
        "HH_GERACAO",
        "AA_ELEICAO",
        "CD_TIPO_ELEICAO",
        "NM_TIPO_ELEICAO",
        "CD_ELEICAO",
        "DS_ELEICAO",
        "DT_ELEICAO",
        "ST_TURNO",
        "TP_PRESTACAO_CONTAS",
        "DT_PRESTACAO_CONTAS",
        "SQ_PRESTADOR_CONTAS",
        "SG_UF",
        "DS_TIPO_DOCUMENTO",
        "NR_DOCUMENTO",
        "CD_FONTE_DESPESA",
        "DS_FONTE_DESPESA",
        "CD_ORIGEM_DESPESA",
        "DS_ORIGEM_DESPESA",
        "CD_NATUREZA_DESPESA",
        "DS_NATUREZA_DESPESA",
        "CD_ESPECIE_RECURSO",
        "DS_ESPECIE_RECURSO",
        "SQ_DESPESA",
        "SQ_PARCELAMENTO_DESPESA",
        "DT_PAGTO_DESPESA",
        "DS_DESPESA",
        "VR_PAGTO_DESPESA",
    ),
    (2022, "receitas_candidatos_2022_BRASIL.csv"): (
        "DT_GERACAO",
        "HH_GERACAO",
        "AA_ELEICAO",
        "CD_TIPO_ELEICAO",
        "NM_TIPO_ELEICAO",
        "CD_ELEICAO",
        "DS_ELEICAO",
        "DT_ELEICAO",
        "ST_TURNO",
        "TP_PRESTACAO_CONTAS",
        "DT_PRESTACAO_CONTAS",
        "SQ_PRESTADOR_CONTAS",
        "SG_UF",
        "SG_UE",
        "NM_UE",
        "NR_CNPJ_PRESTADOR_CONTA",
        "CD_CARGO",
        "DS_CARGO",
        "SQ_CANDIDATO",
        "NR_CANDIDATO",
        "NM_CANDIDATO",
        "NR_CPF_CANDIDATO",
        "NR_CPF_VICE_CANDIDATO",
        "NR_PARTIDO",
        "SG_PARTIDO",
        "NM_PARTIDO",
        "CD_FONTE_RECEITA",
        "DS_FONTE_RECEITA",
        "CD_ORIGEM_RECEITA",
        "DS_ORIGEM_RECEITA",
        "CD_NATUREZA_RECEITA",
        "DS_NATUREZA_RECEITA",
        "CD_ESPECIE_RECEITA",
        "DS_ESPECIE_RECEITA",
        "CD_CNAE_DOADOR",
        "DS_CNAE_DOADOR",
        "NR_CPF_CNPJ_DOADOR",
        "NM_DOADOR",
        "NM_DOADOR_RFB",
        "CD_ESFERA_PARTIDARIA_DOADOR",
        "DS_ESFERA_PARTIDARIA_DOADOR",
        "SG_UF_DOADOR",
        "CD_MUNICIPIO_DOADOR",
        "NM_MUNICIPIO_DOADOR",
        "SQ_CANDIDATO_DOADOR",
        "NR_CANDIDATO_DOADOR",
        "CD_CARGO_CANDIDATO_DOADOR",
        "DS_CARGO_CANDIDATO_DOADOR",
        "NR_PARTIDO_DOADOR",
        "SG_PARTIDO_DOADOR",
        "NM_PARTIDO_DOADOR",
        "NR_RECIBO_DOACAO",
        "NR_DOCUMENTO_DOACAO",
        "SQ_RECEITA",
        "DT_RECEITA",
        "DS_RECEITA",
        "VR_RECEITA",
        "DS_NATUREZA_RECURSO_ESTIMAVEL",
        "DS_GENERO",
        "DS_COR_RACA",
    ),
    (2022, "receitas_candidatos_doador_originario_2022_BRASIL.csv"): (
        "DT_GERACAO",
        "HH_GERACAO",
        "AA_ELEICAO",
        "CD_TIPO_ELEICAO",
        "NM_TIPO_ELEICAO",
        "CD_ELEICAO",
        "DS_ELEICAO",
        "DT_ELEICAO",
        "ST_TURNO",
        "TP_PRESTACAO_CONTAS",
        "DT_PRESTACAO_CONTAS",
        "SQ_PRESTADOR_CONTAS",
        "SG_UF",
        "NR_CPF_CNPJ_DOADOR_ORIGINARIO",
        "NM_DOADOR_ORIGINARIO",
        "NM_DOADOR_ORIGINARIO_RFB",
        "TP_DOADOR_ORIGINARIO",
        "CD_CNAE_DOADOR_ORIGINARIO",
        "DS_CNAE_DOADOR_ORIGINARIO",
        "SQ_RECEITA",
        "DT_RECEITA",
        "DS_RECEITA",
        "VR_RECEITA",
    ),
    (2024, "bem_candidato_2024_BRASIL.csv"): (
        "DT_GERACAO",
        "HH_GERACAO",
        "ANO_ELEICAO",
        "CD_TIPO_ELEICAO",
        "NM_TIPO_ELEICAO",
        "CD_ELEICAO",
        "DS_ELEICAO",
        "DT_ELEICAO",
        "SG_UF",
        "SG_UE",
        "NM_UE",
        "SQ_CANDIDATO",
        "NR_ORDEM_BEM_CANDIDATO",
        "CD_TIPO_BEM_CANDIDATO",
        "DS_TIPO_BEM_CANDIDATO",
        "DS_BEM_CANDIDATO",
        "VR_BEM_CANDIDATO",
        "DT_ULT_ATUAL_BEM_CANDIDATO",
        "HH_ULT_ATUAL_BEM_CANDIDATO",
    ),
    (2024, "consulta_cand_2024_BRASIL.csv"): (
        "DT_GERACAO",
        "HH_GERACAO",
        "ANO_ELEICAO",
        "CD_TIPO_ELEICAO",
        "NM_TIPO_ELEICAO",
        "NR_TURNO",
        "CD_ELEICAO",
        "DS_ELEICAO",
        "DT_ELEICAO",
        "TP_ABRANGENCIA",
        "SG_UF",
        "SG_UE",
        "NM_UE",
        "CD_CARGO",
        "DS_CARGO",
        "SQ_CANDIDATO",
        "NR_CANDIDATO",
        "NM_CANDIDATO",
        "NM_URNA_CANDIDATO",
        "NM_SOCIAL_CANDIDATO",
        "NR_CPF_CANDIDATO",
        "DS_EMAIL",
        "CD_SITUACAO_CANDIDATURA",
        "DS_SITUACAO_CANDIDATURA",
        "TP_AGREMIACAO",
        "NR_PARTIDO",
        "SG_PARTIDO",
        "NM_PARTIDO",
        "NR_FEDERACAO",
        "NM_FEDERACAO",
        "SG_FEDERACAO",
        "DS_COMPOSICAO_FEDERACAO",
        "SQ_COLIGACAO",
        "NM_COLIGACAO",
        "DS_COMPOSICAO_COLIGACAO",
        "SG_UF_NASCIMENTO",
        "DT_NASCIMENTO",
        "NR_TITULO_ELEITORAL_CANDIDATO",
        "CD_GENERO",
        "DS_GENERO",
        "CD_GRAU_INSTRUCAO",
        "DS_GRAU_INSTRUCAO",
        "CD_ESTADO_CIVIL",
        "DS_ESTADO_CIVIL",
        "CD_COR_RACA",
        "DS_COR_RACA",
        "CD_OCUPACAO",
        "DS_OCUPACAO",
        "CD_SIT_TOT_TURNO",
        "DS_SIT_TOT_TURNO",
    ),
    (2024, "despesas_contratadas_candidatos_2024_BRASIL.csv"): (
        "DT_GERACAO",
        "HH_GERACAO",
        "AA_ELEICAO",
        "CD_TIPO_ELEICAO",
        "NM_TIPO_ELEICAO",
        "CD_ELEICAO",
        "DS_ELEICAO",
        "DT_ELEICAO",
        "ST_TURNO",
        "TP_PRESTACAO_CONTAS",
        "DT_PRESTACAO_CONTAS",
        "SQ_PRESTADOR_CONTAS",
        "SG_UF",
        "SG_UE",
        "NM_UE",
        "NR_CNPJ_PRESTADOR_CONTA",
        "CD_CARGO",
        "DS_CARGO",
        "SQ_CANDIDATO",
        "NR_CANDIDATO",
        "NM_CANDIDATO",
        "NR_CPF_CANDIDATO",
        "NR_CPF_VICE_CANDIDATO",
        "NR_PARTIDO",
        "SG_PARTIDO",
        "NM_PARTIDO",
        "CD_TIPO_FORNECEDOR",
        "DS_TIPO_FORNECEDOR",
        "CD_CNAE_FORNECEDOR",
        "DS_CNAE_FORNECEDOR",
        "NR_CPF_CNPJ_FORNECEDOR",
        "NM_FORNECEDOR",
        "NM_FORNECEDOR_RFB",
        "CD_ESFERA_PART_FORNECEDOR",
        "DS_ESFERA_PART_FORNECEDOR",
        "SG_UF_FORNECEDOR",
        "CD_MUNICIPIO_FORNECEDOR",
        "NM_MUNICIPIO_FORNECEDOR",
        "SQ_CANDIDATO_FORNECEDOR",
        "NR_CANDIDATO_FORNECEDOR",
        "CD_CARGO_FORNECEDOR",
        "DS_CARGO_FORNECEDOR",
        "NR_PARTIDO_FORNECEDOR",
        "SG_PARTIDO_FORNECEDOR",
        "NM_PARTIDO_FORNECEDOR",
        "DS_TIPO_DOCUMENTO",
        "NR_DOCUMENTO",
        "CD_ORIGEM_DESPESA",
        "DS_ORIGEM_DESPESA",
        "SQ_DESPESA",
        "DT_DESPESA",
        "DS_DESPESA",
        "VR_DESPESA_CONTRATADA",
    ),
    (2024, "despesas_pagas_candidatos_2024_BRASIL.csv"): (
        "DT_GERACAO",
        "HH_GERACAO",
        "AA_ELEICAO",
        "CD_TIPO_ELEICAO",
        "NM_TIPO_ELEICAO",
        "CD_ELEICAO",
        "DS_ELEICAO",
        "DT_ELEICAO",
        "ST_TURNO",
        "TP_PRESTACAO_CONTAS",
        "DT_PRESTACAO_CONTAS",
        "SQ_PRESTADOR_CONTAS",
        "SG_UF",
        "DS_TIPO_DOCUMENTO",
        "NR_DOCUMENTO",
        "CD_FONTE_DESPESA",
        "DS_FONTE_DESPESA",
        "CD_ORIGEM_DESPESA",
        "DS_ORIGEM_DESPESA",
        "CD_NATUREZA_DESPESA",
        "DS_NATUREZA_DESPESA",
        "CD_ESPECIE_RECURSO",
        "DS_ESPECIE_RECURSO",
        "SQ_DESPESA",
        "SQ_PARCELAMENTO_DESPESA",
        "DT_PAGTO_DESPESA",
        "DS_DESPESA",
        "VR_PAGTO_DESPESA",
    ),
    (2024, "receitas_candidatos_2024_BRASIL.csv"): (
        "DT_GERACAO",
        "HH_GERACAO",
        "AA_ELEICAO",
        "CD_TIPO_ELEICAO",
        "NM_TIPO_ELEICAO",
        "CD_ELEICAO",
        "DS_ELEICAO",
        "DT_ELEICAO",
        "ST_TURNO",
        "TP_PRESTACAO_CONTAS",
        "DT_PRESTACAO_CONTAS",
        "SQ_PRESTADOR_CONTAS",
        "SG_UF",
        "SG_UE",
        "NM_UE",
        "NR_CNPJ_PRESTADOR_CONTA",
        "CD_CARGO",
        "DS_CARGO",
        "SQ_CANDIDATO",
        "NR_CANDIDATO",
        "NM_CANDIDATO",
        "NR_CPF_CANDIDATO",
        "NR_CPF_VICE_CANDIDATO",
        "NR_PARTIDO",
        "SG_PARTIDO",
        "NM_PARTIDO",
        "CD_FONTE_RECEITA",
        "DS_FONTE_RECEITA",
        "CD_ORIGEM_RECEITA",
        "DS_ORIGEM_RECEITA",
        "CD_NATUREZA_RECEITA",
        "DS_NATUREZA_RECEITA",
        "CD_ESPECIE_RECEITA",
        "DS_ESPECIE_RECEITA",
        "CD_CNAE_DOADOR",
        "DS_CNAE_DOADOR",
        "NR_CPF_CNPJ_DOADOR",
        "NM_DOADOR",
        "NM_DOADOR_RFB",
        "CD_ESFERA_PARTIDARIA_DOADOR",
        "DS_ESFERA_PARTIDARIA_DOADOR",
        "SG_UF_DOADOR",
        "CD_MUNICIPIO_DOADOR",
        "NM_MUNICIPIO_DOADOR",
        "SQ_CANDIDATO_DOADOR",
        "NR_CANDIDATO_DOADOR",
        "CD_CARGO_CANDIDATO_DOADOR",
        "DS_CARGO_CANDIDATO_DOADOR",
        "NR_PARTIDO_DOADOR",
        "SG_PARTIDO_DOADOR",
        "NM_PARTIDO_DOADOR",
        "NR_RECIBO_DOACAO",
        "NR_DOCUMENTO_DOACAO",
        "SQ_RECEITA",
        "DT_RECEITA",
        "DS_RECEITA",
        "VR_RECEITA",
        "DS_NATUREZA_RECURSO_ESTIMAVEL",
        "DS_GENERO",
        "DS_COR_RACA",
    ),
    (2024, "receitas_candidatos_doador_originario_2024_BRASIL.csv"): (
        "DT_GERACAO",
        "HH_GERACAO",
        "AA_ELEICAO",
        "CD_TIPO_ELEICAO",
        "NM_TIPO_ELEICAO",
        "CD_ELEICAO",
        "DS_ELEICAO",
        "DT_ELEICAO",
        "ST_TURNO",
        "TP_PRESTACAO_CONTAS",
        "DT_PRESTACAO_CONTAS",
        "SQ_PRESTADOR_CONTAS",
        "SG_UF",
        "NR_CPF_CNPJ_DOADOR_ORIGINARIO",
        "NM_DOADOR_ORIGINARIO",
        "NM_DOADOR_ORIGINARIO_RFB",
        "TP_DOADOR_ORIGINARIO",
        "CD_CNAE_DOADOR_ORIGINARIO",
        "DS_CNAE_DOADOR_ORIGINARIO",
        "SQ_RECEITA",
        "DT_RECEITA",
        "DS_RECEITA",
        "VR_RECEITA",
    ),
}


def csv_sintetico(header, linhas=None):
    linhas = linhas if linhas is not None else [["Á sintético"] * len(header)]
    return (";".join(header) + "\n" + "".join(";".join(linha) + "\n" for linha in linhas)).encode(
        "latin-1"
    )


def preparar(tmp_path, recurso, membros, ano=2024, **kwargs):
    original = tmp_path / "original.zip"
    original.write_bytes(zip_tse(membros))
    return preparar_familias(recurso, Competencia.de_ano(ano), original, tmp_path, **kwargs)


@respx.mock
def test_contas_um_download_quatro_familias(tmp_path):
    recurso = recurso_tse("contas")
    membros = {
        nome.format(ano=2024): csv_sintetico(CABECALHOS[2024, nome.format(ano=2024)])
        for nome in recurso.familias.values()
    }
    rota = respx.get(recurso.url.format(ano=2024)).mock(
        return_value=httpx.Response(200, content=zip_tse(membros))
    )
    http = ClienteHttp()
    try:
        extraido = extrair(recurso, Competencia.de_ano(2024), tmp_path, http, date(2026, 10, 7))
        familias = preparar_familias(
            recurso, extraido.competencia, extraido.arquivo_original, tmp_path
        )
    finally:
        http.fechar()
    downloads = rota.call_count
    assert downloads == 1
    assert {f.familia for f in familias} == {
        "receitas",
        "contratadas",
        "pagamentos",
        "doador_originario",
    }
    assert extraido.extensao == "zip"
    assert all(f.csv.exists() for f in familias)


@pytest.mark.parametrize("recurso_id", ["candidaturas", "bens", "contas"])
def test_consolidado_sem_ufs(tmp_path, recurso_id):
    recurso = recurso_tse(recurso_id)
    nomes = [n.format(ano=2024) for n in recurso.familias.values()]
    membros = {n: csv_sintetico(CABECALHOS[2024, n]) for n in nomes}
    membros.update({n.replace("BRASIL", "SP"): b"UF ignorada" for n in nomes})
    familias = preparar(tmp_path, recurso, membros)
    for familia, nome in zip(familias, nomes, strict=True):
        assert [familia.membro] == [nome]
        assert familia.csv.read_bytes() == membros[nome]
        assert familia.layout_id == f"tse:{familia.familia}:2024:v1"
    assert len(familias) == len(nomes)


@pytest.mark.parametrize("ano,nome", CABECALHOS)
def test_layout_publico_por_ano(tmp_path, ano, nome):
    recurso_id = (
        "candidaturas"
        if nome.startswith("consulta")
        else "bens"
        if nome.startswith("bem_")
        else "contas"
    )
    recurso = recurso_tse(recurso_id)
    recurso = recurso.model_copy(
        update={
            "familias": {f: n for f, n in recurso.familias.items() if n.format(ano=ano) == nome}
        }
    )
    familias = preparar(tmp_path, recurso, {nome: csv_sintetico(CABECALHOS[ano, nome])}, ano)
    assert len(familias) == 1
    assert familias[0].csv.read_bytes().decode("latin-1").endswith("Á sintético\n")


@pytest.mark.parametrize("ano,nome", CABECALHOS)
def test_campo_essencial_ausente_falha(tmp_path, ano, nome):
    recurso_id = (
        "candidaturas"
        if nome.startswith("consulta")
        else "bens"
        if nome.startswith("bem_")
        else "contas"
    )
    recurso = recurso_tse(recurso_id)
    recurso = recurso.model_copy(
        update={
            "familias": {f: n for f, n in recurso.familias.items() if n.format(ano=ano) == nome}
        }
    )
    essencial = (
        "SQ_RECEITA"
        if "doador_originario" in nome
        else "SQ_PARCELAMENTO_DESPESA"
        if "despesas_pagas" in nome
        else "SQ_CANDIDATO"
    )
    header = [c for c in CABECALHOS[ano, nome] if c != essencial]
    with pytest.raises(ErroColeta, match="cabeçalho"):
        preparar(tmp_path, recurso, {nome: csv_sintetico(header)}, ano)
    assert not list(tmp_path.glob("tse_*.csv"))


@pytest.mark.parametrize(
    "defeito", ["ausente", "duplicado", "header", "header_repetido", "linha_truncada", "aspas"]
)
def test_membro_invalido_nao_prepara(tmp_path, defeito):
    nome = "consulta_cand_2024_BRASIL.csv"
    header = CABECALHOS[2024, nome]
    corpo = csv_sintetico(header)
    if defeito == "header":
        corpo = csv_sintetico([*header, "DESCONHECIDA"])
    if defeito == "header_repetido":
        corpo = csv_sintetico(header, [list(header)])
    if defeito == "linha_truncada":
        corpo = csv_sintetico(header, [["incompleta"]])
    if defeito == "aspas":
        corpo = (";".join(header) + '\n"sem fim').encode("latin-1")
    original = tmp_path / "original.zip"
    with zipfile.ZipFile(original, "w") as z:
        z.writestr("outro.csv" if defeito == "ausente" else nome, corpo)
        if defeito == "duplicado":
            with pytest.warns(UserWarning):
                z.writestr(nome, corpo)
    with pytest.raises(ErroColeta):
        preparar_familias(recurso_tse("candidaturas"), Competencia.de_ano(2024), original, tmp_path)
    assert not list(tmp_path.glob("tse_*.csv"))


def test_limite_por_membro(tmp_path):
    nome = "consulta_cand_2024_BRASIL.csv"
    with pytest.raises(ErroColeta, match="teto"):
        preparar(tmp_path, recurso_tse("candidaturas"), {nome: b"x" * 33}, limite_membro_bytes=32)


def test_crc_invalido_nao_prepara(tmp_path):
    nome = "consulta_cand_2024_BRASIL.csv"
    corpo = csv_sintetico(CABECALHOS[2024, nome], [["sintético"] * 50] * 5000)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as z:
        z.writestr(nome, corpo)
    quebrado = bytearray(buffer.getvalue())
    inicio = 30 + len(nome)
    quebrado[inicio + len(corpo) - 10] ^= 1
    original = tmp_path / "original.zip"
    original.write_bytes(quebrado)
    with pytest.raises(ErroColeta, match="CRC"):
        preparar_familias(recurso_tse("candidaturas"), Competencia.de_ano(2024), original, tmp_path)
    assert not list(tmp_path.glob("tse_*.csv"))


def test_zip_truncado(tmp_path):
    original = tmp_path / "original.zip"
    original.write_bytes(zip_tse({"x": b"x"})[:-30])
    with pytest.raises(ErroColeta):
        preparar_familias(recurso_tse("bens"), Competencia.de_ano(2024), original, tmp_path)


def test_ano_desconhecido(tmp_path):
    with pytest.raises(ErroColeta, match="ano"):
        preparar(tmp_path, recurso_tse("bens"), {}, 2019)


def test_teto_individual_nao_soma_familias(tmp_path):
    recurso = recurso_tse("contas")
    membros = {
        n.format(ano=2024): csv_sintetico(CABECALHOS[2024, n.format(ano=2024)])
        for n in recurso.familias.values()
    }
    teto = max(map(len, membros.values()))
    assert sum(map(len, membros.values())) > teto
    assert len(preparar(tmp_path, recurso, membros, limite_membro_bytes=teto)) == 4


def test_falha_ultima_familia_remove_anteriores(tmp_path):
    recurso = recurso_tse("contas")
    membros = {
        n.format(ano=2024): csv_sintetico(CABECALHOS[2024, n.format(ano=2024)])
        for n in recurso.familias.values()
    }
    membros["receitas_candidatos_doador_originario_2024_BRASIL.csv"] = b"invalido"
    with pytest.raises(ErroColeta):
        preparar(tmp_path, recurso, membros)
    assert not list(tmp_path.glob("tse_*.csv"))


def test_preserva_preparacao_anterior(tmp_path):
    destino = tmp_path / "tse_bens_2024.csv"
    destino.write_bytes(b"anterior")
    nome = "bem_candidato_2024_BRASIL.csv"
    with pytest.raises(FileExistsError):
        preparar(tmp_path, recurso_tse("bens"), {nome: csv_sintetico(CABECALHOS[2024, nome])})
    assert destino.read_bytes() == b"anterior"


def test_descompacta_em_blocos_limitados(tmp_path, monkeypatch):
    ler = zipfile.ZipExtFile.read
    tamanhos = []

    def ler_limitado(self, n=-1):
        assert 0 < n <= 1 << 20
        tamanhos.append(n)
        return ler(self, n)

    monkeypatch.setattr(zipfile.ZipExtFile, "read", ler_limitado)
    nome = "bem_candidato_2024_BRASIL.csv"
    corpo = csv_sintetico(CABECALHOS[2024, nome], [["x"] * 19] * 100000)
    familias = preparar(tmp_path, recurso_tse("bens"), {nome: corpo})
    assert familias[0].csv.stat().st_size == len(corpo)
    assert len(tamanhos) >= 4


@pytest.mark.parametrize(
    "familias",
    [
        {"bens": "bem_candidato_{ano}_SP.csv"},
        {"bens": "bem_candidato_{ano}_*.csv"},
        {"desconhecida": "bem_candidato_{ano}_BRASIL.csv"},
    ],
)
def test_template_nao_aprovado(tmp_path, familias):
    recurso = recurso_tse("bens").model_copy(update={"familias": familias})
    with pytest.raises(ErroColeta):
        preparar(tmp_path, recurso, {})


def test_extrair_exige_competencia(tmp_path):
    with pytest.raises(ErroColeta, match="anual"):
        extrair(recurso_tse("bens"), None, tmp_path, None, date(2026, 10, 7))


def test_deflate_corrompido_erro_coleta(tmp_path):
    nome = "bem_candidato_2024_BRASIL.csv"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(nome, csv_sintetico(CABECALHOS[2024, nome]))
    quebrado = bytearray(buffer.getvalue())
    quebrado[30 + len(nome)] = 7  # Tipo de bloco DEFLATE reservado/inválido.
    original = tmp_path / "original.zip"
    original.write_bytes(quebrado)
    with pytest.raises(ErroColeta):
        preparar_familias(recurso_tse("bens"), Competencia.de_ano(2024), original, tmp_path)
    assert not list(tmp_path.glob("tse_*.csv"))
