-- Autores de emenda e a ligação com o cadastro de parlamentares (onda A). A ligação é pelo nome
-- normalizado e só vale para autor individual com exatamente um parlamentar de mesmo nome.
with autores as (
    select autor_codigo, autor_nome, tipo_emenda from {{ ref('stg_cgu__emendas') }}
    union all
    select autor_codigo, autor_nome, tipo_emenda from {{ ref('stg_cgu__emendas_favorecidos') }}
    union all
    select autor_codigo, autor_nome, tipo_emenda from {{ ref('stg_cgu__emendas_documentos') }}
),

por_autor as (
    select
        autor_codigo,
        mode(autor_nome) as autor_nome,
        mode(tipo_emenda) as tipo_emenda
    from autores
    where autor_codigo is not null
    group by autor_codigo
),

classificados as (
    select
        *,
        case
            when tipo_emenda ilike '%individual%' then 'parlamentar'
            when tipo_emenda ilike '%bancada%' then 'bancada'
            when tipo_emenda ilike '%comiss%' then 'comissao'
            when tipo_emenda ilike '%relator%' then 'relator'
            else 'outro'
        end as tipo_autor,
        {{ nome_normalizado('autor_nome') }} as nome_chave
    from por_autor
),

candidatos as (
    select
        {{ nome_normalizado('nome') }} as nome_chave,
        count(*) as quantidade,
        any_value(parlamentar_id) as parlamentar_id
    from {{ ref('dim_parlamentar') }}
    group by 1
)

select
    c.autor_codigo,
    c.autor_nome,
    c.tipo_autor,
    if(c.tipo_autor = 'parlamentar' and p.quantidade = 1, p.parlamentar_id, null) as parlamentar_id,
    coalesce(p.quantidade, 0) as parlamentares_com_o_nome
from classificados as c
left join candidatos as p
    on p.nome_chave = c.nome_chave
