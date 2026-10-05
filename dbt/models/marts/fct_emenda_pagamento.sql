{{
    config(
        location=env_var('ELEITORADO_PUBLICO', 'dados/publico') ~ '/marts/fct_emenda_pagamento',
        options={'partition_by': 'ano_documento', 'overwrite_or_ignore': True, 'compression': 'zstd'},
    )
}}

-- Documentos de despesa de emendas (empenho, liquidação, pagamento). CPF sempre mascarado.
select
    pagamento_linha_id,
    emenda_codigo,
    ano_emenda,
    autor_codigo,
    numero_emenda,
    tipo_emenda,
    data_documento,
    coalesce(year(data_documento), cast(left(_competencia, 4) as integer)) as ano_documento,
    documento_codigo,
    fase_despesa,
    valor_empenhado,
    valor_pago,
    localidade, uf_sigla, municipio_id,
    {{ documento_publico('favorecido_documento') }} as favorecido_documento,
    favorecido_tipo_documento,
    favorecido_cnpj_raiz,
    {{ mascarar_cpfs_em_texto('favorecido_nome') }} as favorecido_nome,
    tipo_favorecido, favorecido_uf, favorecido_municipio,
    ug_codigo, ug_nome, orgao_codigo, orgao_nome, orgao_superior_codigo, orgao_superior_nome,
    grupo_despesa, elemento_despesa, modalidade_aplicacao, funcao, subfuncao, programa, acao,
    possui_convenio,
    _coleta_id
from {{ ref('int_cgu__emendas_pagamentos') }}
