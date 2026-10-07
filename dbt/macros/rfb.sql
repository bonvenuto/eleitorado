{#- Fatos com CNPJ que os alertas da onda C1 cruzam com o cadastro da Receita: despesa de cota,
    pagamento de emenda e contrato federal. Registros com problema de qualidade ficam de fora
    (data de emissão impossível na cota, valor implausível no contrato). -#}
{% macro rfb_fatos() -%}
select
    'cota' as origem,
    despesa_id as fato_id,
    data_emissao as data_fato,
    valor_documento as valor,
    fornecedor_documento as cnpj,
    fornecedor_cnpj_raiz as cnpj_raiz,
    parlamentar_id
from {{ ref('fct_despesa_cota_parlamentar') }}
where fornecedor_tipo_documento = 'CNPJ' and data_emissao_valida
union all
select
    'emenda' as origem,
    p.pagamento_linha_id as fato_id,
    p.data_documento as data_fato,
    p.valor_pago as valor,
    p.favorecido_documento as cnpj,
    p.favorecido_cnpj_raiz as cnpj_raiz,
    a.parlamentar_id
from {{ ref('fct_emenda_pagamento') }} as p
left join {{ ref('dim_autor_emenda') }} as a on a.autor_codigo = p.autor_codigo
where p.fase_despesa = 'Pagamento' and p.favorecido_tipo_documento = 'CNPJ'
    and p.data_documento is not null
union all
select
    'contrato' as origem,
    contrato_id as fato_id,
    data_assinatura as data_fato,
    valor_final as valor,
    fornecedor_documento as cnpj,
    fornecedor_cnpj_raiz as cnpj_raiz,
    cast(null as varchar) as parlamentar_id
from {{ ref('fct_contrato_federal') }}
where fornecedor_tipo_documento = 'CNPJ' and not valor_suspeito and data_assinatura is not null
{%- endmacro %}
