{{
    config(
        location=env_var('ELEITORADO_PUBLICO', 'dados/publico') ~ '/marts/fct_licitacao_vencedor',
        options={'partition_by': 'ano_competencia', 'overwrite_or_ignore': True, 'compression': 'zstd'},
    )
}}

-- Vencedores de licitações federais (2013 a 2024-04), por item. CPF mascarado. Os demais
-- participantes ficam no lago privado (intermediate).
select
    participante_linha_id,
    licitacao_id,
    licitacao_numero, ug_codigo, modalidade_codigo, orgao_codigo, orgao_nome,
    item_codigo, item_descricao,
    {{ documento_publico('participante_documento') }} as participante_documento,
    participante_tipo_documento,
    participante_cnpj_raiz,
    {{ mascarar_cpfs_em_texto('participante_nome') }} as participante_nome,
    data_licitacao,
    cast(left(_competencia, 4) as integer) as ano_competencia,
    _coleta_id
from {{ ref('int_cgu__licitacao_participantes') }}
where vencedor
