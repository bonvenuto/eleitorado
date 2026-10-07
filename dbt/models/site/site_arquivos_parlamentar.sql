-- Um arquivo por parlamentar (`parlamentar/<casa>-<id>.json`, spec do site, seção 4.2): cota por
-- ano, por categoria e os 20 maiores fornecedores; emendas de autoria por ano e os 20 maiores
-- favorecidos; alertas (os `site_max_alertas` mais recentes e o total).
with cota as (
    select * from {{ ref('site_cota') }}
),

emendas as (
    select * from {{ ref('site_emendas') }} where parlamentar_id is not null
),

cota_total as (
    select parlamentar_id, sum(valor) as total from cota group by parlamentar_id
),

cota_ano as (
    select parlamentar_id, list({'ano': ano, 'valor': valor} order by ano) as itens
    from (select parlamentar_id, ano, sum(valor) as valor from cota group by parlamentar_id, ano)
    group by parlamentar_id
),

cota_categoria as (
    select
        parlamentar_id,
        list({'categoria': categoria, 'valor': valor} order by valor desc, categoria) as itens
    from (
        select parlamentar_id, categoria, sum(valor) as valor
        from cota group by parlamentar_id, categoria
    )
    group by parlamentar_id
),

cota_fornecedor as (
    select
        parlamentar_id,
        list(
            {
                'nome': nome, 'documento': documento, 'cnpj_raiz': cnpj_raiz, 'valor': valor,
                'despesas': despesas
            }
            order by valor desc, nome
        ) as itens
    from (
        select
            parlamentar_id,
            fornecedor_documento as documento,
            max(fornecedor_nome) as nome,
            max(fornecedor_cnpj_raiz) as cnpj_raiz,
            sum(valor) as valor,
            sum(despesas) as despesas
        from cota
        group by parlamentar_id, fornecedor_documento
        qualify row_number() over (
            partition by parlamentar_id order by sum(valor) desc, max(fornecedor_nome)
        ) <= {{ var('site_top') }}
    )
    group by parlamentar_id
),

emendas_ano as (
    select parlamentar_id, sum(pago) as total, list({'ano': ano, 'pago': pago} order by ano) as itens
    from (
        select parlamentar_id, ano, sum(pago) as pago from emendas group by parlamentar_id, ano
    )
    group by parlamentar_id
),

emendas_favorecido as (
    select
        parlamentar_id,
        list(
            {'nome': nome, 'documento': documento, 'cnpj_raiz': cnpj_raiz, 'pago': pago}
            order by pago desc, nome
        ) as itens
    from (
        select
            parlamentar_id,
            favorecido_documento as documento,
            max(favorecido_nome) as nome,
            max(favorecido_cnpj_raiz) as cnpj_raiz,
            sum(pago) as pago
        from emendas
        group by parlamentar_id, favorecido_documento
        qualify row_number() over (
            partition by parlamentar_id order by sum(pago) desc, max(favorecido_nome)
        ) <= {{ var('site_top') }}
    )
    group by parlamentar_id
),

alertas as (
    select
        parlamentar_id,
        count(*) as total,
        list({{ site_alerta_json() }} order by {{ site_ordem_alertas() }})
            filter (where ordem <= {{ var('site_max_alertas') }}) as itens
    from (
        select
            *,
            row_number() over (
                partition by parlamentar_id order by {{ site_ordem_alertas() }}
            ) as ordem
        from {{ ref('site_alertas') }}
        where parlamentar_id is not null
    )
    group by parlamentar_id
)

select
    'parlamentar/' || replace(p.parlamentar_id, ':', '-') || '.json' as caminho,
    to_json({
        'esquema': 1,
        'parlamentar': {
            'id': p.parlamentar_id,
            'nome': p.nome,
            'casa': p.casa,
            'uf': p.uf_sigla,
            'partido': p.partido_sigla,
            'foto': p.url_foto,
            'legislaturas': coalesce(p.legislaturas, []),
            'url_oficial': if(
                p.casa = 'camara',
                'https://www.camara.leg.br/deputados/' || p.id_origem,
                'https://www25.senado.leg.br/web/senadores/senador/-/perfil/' || p.id_origem
            )
        },
        'cota': {
            'total': coalesce(ct.total, 0),
            'por_ano': coalesce(ca.itens, []),
            'por_categoria': coalesce(cc.itens, []),
            'fornecedores': coalesce(cf.itens, [])
        },
        'emendas': {
            'total_pago': coalesce(ea.total, 0),
            'por_ano': coalesce(ea.itens, []),
            'favorecidos': coalesce(ef.itens, [])
        },
        'alertas': {'total': coalesce(al.total, 0), 'itens': coalesce(al.itens, [])}
    })::varchar as conteudo,
    coalesce(al.total, 0) as alertas_total,
    coalesce(len(al.itens), 0) as alertas_no_arquivo,
    coalesce(len(cf.itens), 0) as fornecedores_no_arquivo
from {{ ref('dim_parlamentar') }} as p
left join cota_total as ct on ct.parlamentar_id = p.parlamentar_id
left join cota_ano as ca on ca.parlamentar_id = p.parlamentar_id
left join cota_categoria as cc on cc.parlamentar_id = p.parlamentar_id
left join cota_fornecedor as cf on cf.parlamentar_id = p.parlamentar_id
left join emendas_ano as ea on ea.parlamentar_id = p.parlamentar_id
left join emendas_favorecido as ef on ef.parlamentar_id = p.parlamentar_id
left join alertas as al on al.parlamentar_id = p.parlamentar_id
