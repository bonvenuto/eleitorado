-- Estabelecimentos na competência mais recente da Receita, com as descrições dos códigos e o
-- município IBGE. Tem endereço e contato: fica no lago privado.
with codigos as (
    select * from {{ ref('stg_rfb__codigos') }}
    where competencia = (select max(competencia) from {{ ref('stg_rfb__codigos') }})
)

select
    e.* exclude (competencia),
    e.competencia as competencia_receita,
    case e.situacao_codigo
        when '01' then 'NULA'
        when '02' then 'ATIVA'
        when '03' then 'SUSPENSA'
        when '04' then 'INAPTA'
        when '08' then 'BAIXADA'
    end as situacao,
    m.descricao as motivo,
    c.descricao as cnae_principal_descricao,
    mun.municipio_id
from {{ ref('stg_rfb__estabelecimentos') }} as e
left join codigos as m on m.tabela = 'motivos' and m.codigo = e.motivo_codigo
left join codigos as c on c.tabela = 'cnaes' and c.codigo = e.cnae_principal
left join {{ ref('int_rfb__municipios') }} as mun
    on mun.municipio_rfb_codigo = e.municipio_rfb_codigo and mun.uf_sigla = e.uf_sigla
where e.competencia = (select max(competencia) from {{ ref('stg_rfb__estabelecimentos') }})
