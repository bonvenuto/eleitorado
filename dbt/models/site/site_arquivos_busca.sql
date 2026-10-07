-- Índice de busca (spec do site, seção 4.2). Parlamentares num arquivo só. Empresas em blocos pelas
-- 3 primeiras letras de cada palavra da razão social (sem acento, minúsculas, 3 ou mais
-- caracteres, fora das palavras comuns); bloco com mais de `site_busca_max` empresas é
-- subdividido em blocos de 4 letras e fica só com as empresas de palavra de exatamente 3 letras.
{%- set comuns = [
    'ltda', 'me', 'epp', 'eireli', 'sa', 's/a', 'cia', 'de', 'da', 'do', 'das', 'dos', 'e',
    'comercio', 'servicos', 'industria',
] %}
with empresas as (
    select cnpj_raiz, razao_social, uf_sigla, situacao from {{ ref('dim_empresa') }}
),

palavras as (
    select distinct cnpj_raiz, palavra
    from (
        select
            cnpj_raiz,
            unnest(
                regexp_split_to_array(
                    lower(strip_accents(coalesce(razao_social, ''))), '[^a-z0-9]+'
                )
            ) as palavra
        from empresas
    )
    where length(palavra) >= 3
        and palavra not in ('{{ comuns | join("', '") }}')
),

contagem as (
    select left(palavra, 3) as prefixo3, count(distinct cnpj_raiz) as empresas
    from palavras
    group by left(palavra, 3)
),

entradas as (
    select distinct
        p.cnpj_raiz,
        if(c.empresas > {{ var('site_busca_max') }}, left(p.palavra, 4), left(p.palavra, 3))
            as prefixo
    from palavras as p
    join contagem as c on c.prefixo3 = left(p.palavra, 3)
),

blocos as (
    select
        n.prefixo,
        list(
            {'raiz': e.cnpj_raiz, 'nome': e.razao_social, 'uf': e.uf_sigla, 'situacao': e.situacao}
            order by e.razao_social, e.cnpj_raiz
        ) as itens
    from entradas as n
    join empresas as e on e.cnpj_raiz = n.cnpj_raiz
    group by n.prefixo
),

subdivididos as (
    select prefixo3 as prefixo from contagem where empresas > {{ var('site_busca_max') }}
),

prefixos as (
    select prefixo from blocos
    union
    select prefixo from subdivididos
)

select
    'busca/empresas/p_' || x.prefixo || '.json' as caminho,
    to_json({
        'esquema': 1,
        'prefixo': x.prefixo,
        'subdividido': s.prefixo is not null,
        'empresas': coalesce(b.itens, [])
    })::varchar as conteudo,
    s.prefixo is not null as subdividido,
    coalesce(len(b.itens), 0) as empresas_no_arquivo
from prefixos as x
left join blocos as b on b.prefixo = x.prefixo
left join subdivididos as s on s.prefixo = x.prefixo

union all
select
    'busca/parlamentares.json',
    to_json({
        'esquema': 1,
        'parlamentares': coalesce(
            list(
                {
                    'id': parlamentar_id, 'nome': nome, 'casa': casa, 'uf': uf_sigla,
                    'partido': partido_sigla, 'foto': url_foto,
                    'legislaturas': coalesce(legislaturas, [])
                }
                order by nome, parlamentar_id
            ),
            []
        )
    })::varchar,
    null,
    count(*)
from {{ ref('dim_parlamentar') }}
