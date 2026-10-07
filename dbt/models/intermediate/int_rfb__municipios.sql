-- Código de município da Receita para o código IBGE: a Receita usa tabela própria. A
-- correspondência é pelo nome sem acentos nem pontuação e pela UF (a UF vem dos estabelecimentos,
-- porque a tabela da Receita não a tem). Município sem correspondência única fica de fora.
with receita as (
    select distinct
        e.municipio_rfb_codigo,
        e.uf_sigla,
        regexp_replace(upper(strip_accents(c.descricao)), '[^A-Z0-9]', '', 'g') as nome
    from {{ ref('stg_rfb__estabelecimentos') }} as e
    join {{ ref('stg_rfb__codigos') }} as c
        on c.tabela = 'municipios'
        and c.codigo = e.municipio_rfb_codigo
        and c.competencia = e.competencia
    where e.uf_sigla != 'EX'
),

ibge as (
    select
        municipio_id,
        uf_sigla,
        regexp_replace(upper(strip_accents(municipio_nome)), '[^A-Z0-9]', '', 'g') as nome
    from {{ ref('stg_ibge__municipios') }}
)

select distinct r.municipio_rfb_codigo, r.uf_sigla, i.municipio_id
from receita as r
join ibge as i
    on i.uf_sigla = r.uf_sigla and i.nome = r.nome
qualify count(distinct i.municipio_id) over (partition by r.municipio_rfb_codigo, r.uf_sigla) = 1
