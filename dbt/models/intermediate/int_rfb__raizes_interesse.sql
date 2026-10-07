{{ config(
    materialized='external',
    location=env_var('ELEITORADO_LAGO', 'dados') ~ '/estado/rfb_raizes_interesse.parquet'
) }}
-- Raízes de CNPJ (8 posições) que aparecem nos dados do eleitorado, com a origem de cada uma: o
-- recorte da base da Receita. Vai para um Parquet em `estado/` no lago, que o pipeline diário
-- sincroniza com o bucket: a coleta da Receita (fora do GitHub, que ela bloqueia) só restaura
-- esse arquivo, sem rodar o dbt.
with origens as (
    select fornecedor_cnpj_raiz as raiz, 'cota' as origem from {{ ref('int_cota__despesas') }}
    union all
    select fornecedor_cnpj_raiz, 'contrato' from {{ ref('int_contratos_federais') }}
    union all
    select favorecido_cnpj_raiz, 'emenda_pagamento' from {{ ref('int_cgu__emendas_pagamentos') }}
    union all
    select
        if(favorecido_tipo_documento = 'CNPJ', substr(favorecido_documento, 1, 8), null),
        'emenda_favorecido'
    from {{ ref('stg_cgu__emendas_favorecidos') }}
    union all
    select participante_cnpj_raiz, 'licitacao' from {{ ref('int_cgu__licitacao_participantes') }}
    union all
    select {{ cnpj_raiz('documento') }}, 'sancao' from {{ ref('int_cgu__sancoes_eventos') }}
    union all
    select {{ cnpj_raiz('fornecedor_cnpj') }}, 'tse_' || tipo_fato
    from {{ ref('fct_despesa_campanha_pj') }}
    where tipo_fato in ('contratacao', 'pagamento') and data is not null
        and valor is not null and valor <> -4
)

select raiz, list(distinct origem order by origem) as origens
from origens
where raiz is not null
group by raiz
