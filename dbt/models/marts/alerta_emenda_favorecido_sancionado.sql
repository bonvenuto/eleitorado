-- Pagamento de emenda a favorecido que tinha sanção vigente na data do documento. O CPF de
-- favorecido já vem mascarado pela fonte, então só pessoas jurídicas cruzam. Indício para investigar.
with pagamentos as (
    select
        *,
        {{ chave_correspondencia('favorecido_tipo_documento', 'favorecido_documento') }} as chave
    from {{ ref('int_cgu__emendas_pagamentos') }}
    where favorecido_documento_valido and data_documento is not null
),

sancoes as (
    {{ sancoes_para_alerta() }}
),

cruzadas as (
    select
        p.pagamento_linha_id,
        s.sancao_id,
        {{ tipo_correspondencia('p.favorecido_tipo_documento', 'p.favorecido_documento', 's.documento') }}
            as tipo_correspondencia,
        p.emenda_codigo,
        p.autor_codigo,
        p.documento_codigo,
        p.fase_despesa,
        p.data_documento,
        p.valor_pago,
        {{ mascarar_cpfs_em_texto('p.favorecido_nome') }} as favorecido_nome,
        {{ documento_publico('p.favorecido_documento') }} as favorecido_documento,
        s.cadastro,
        s.categoria as categoria_sancao,
        s.abrangencia,
        s.orgao_sancionador,
        s.data_inicio as sancao_data_inicio,
        s.data_fim as sancao_data_fim,
        p._coleta_id as pagamento_coleta_id,
        s._coleta_id as sancao_coleta_id,
        s.data_evento as sancao_data_evento
    from pagamentos as p
    join sancoes as s
        on s.chave = p.chave
        and p.data_documento between s.data_inicio and coalesce(s.data_fim, date '9999-12-31')
)

select
    md5(concat('emenda_favorecido_sancionado|', pagamento_linha_id, '|', sancao_id)) as alerta_id,
    * exclude (sancao_data_evento),
    'Documento de despesa de emenda a favorecido com sanção vigente no CEIS/CNEP na data do documento '
    || '(correspondência por CNPJ ou raiz do CNPJ)' as regra
from cruzadas
qualify row_number() over (
    partition by pagamento_linha_id, sancao_id
    order by if(tipo_correspondencia = 'cnpj_raiz', 1, 0), sancao_data_evento desc
) = 1
