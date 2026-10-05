{{
    config(
        location=env_var('ELEITORADO_PUBLICO', 'dados/publico') ~ '/marts/fct_despesa_cota_parlamentar',
        options={'partition_by': 'casa, ano', 'overwrite_or_ignore': True, 'compression': 'zstd'},
    )
}}

-- Uma linha de despesa publicada da CEAP (Câmara) ou da CEAPS (Senado).
-- CPF de fornecedor pessoa física sai mascarado.
select
    despesa_id,
    casa,
    parlamentar_id,
    tipo_beneficiario,
    nome_beneficiario,
    uf_sigla,
    partido_sigla,
    ano,
    mes,
    data_competencia,
    data_emissao,
    categoria,
    subcategoria,
    {{ mascarar_cpfs_em_texto('fornecedor_nome') }} as fornecedor_nome,
    {{ documento_publico('fornecedor_documento') }} as fornecedor_documento,
    fornecedor_tipo_documento,
    fornecedor_documento_valido,
    fornecedor_cnpj_raiz,
    valor_documento,
    valor_glosa,
    valor_reembolsado,
    numero_documento,
    url_documento,
    id_documento_origem,
    {{ mascarar_cpfs_em_texto('camara_passageiro') }} as camara_passageiro,
    camara_trecho,
    {{ mascarar_cpfs_em_texto('senado_detalhamento') }} as senado_detalhamento,
    _coleta_id
from {{ ref('int_cota__despesas') }}
