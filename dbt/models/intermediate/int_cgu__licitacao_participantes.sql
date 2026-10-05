-- Participantes de licitações com a data da licitação e o documento completo (para os alertas).
with licitacoes as (
    select
        ug_codigo, modalidade_codigo, licitacao_numero,
        coalesce(max(data_abertura), max(data_resultado)) as data_licitacao
    from {{ ref('stg_cgu__licitacoes') }}
    group by all
)

select
    md5(concat(p.hash_linha, '-', cast(row_number() over (partition by p.hash_linha order by p._competencia) as varchar)))
        as participante_linha_id,
    concat('cgu:', p.ug_codigo, ':', p.modalidade_codigo, ':', p.licitacao_numero) as licitacao_id,
    p.*,
    l.data_licitacao,
    case p.participante_tipo_documento
        when 'CPF' then {{ documento_valido('p.participante_documento') }}
        when 'CNPJ' then {{ documento_valido('p.participante_documento') }}
        when 'INVALIDO' then false
    end as participante_documento_valido,
    if(p.participante_tipo_documento = 'CNPJ', substr(p.participante_documento, 1, 8), null)
        as participante_cnpj_raiz
from {{ ref('stg_cgu__licitacoes_participantes') }} as p
left join licitacoes as l
    on l.ug_codigo = p.ug_codigo
    and l.modalidade_codigo = p.modalidade_codigo
    and l.licitacao_numero = p.licitacao_numero
