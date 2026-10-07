-- Empresas em blocos pelos 3 primeiros caracteres da raiz do CNPJ (`empresa/<abc>.json`, spec do
-- site, seção 4.2): cadastro na Receita (sem sócios, endereço nem contato), o que recebeu (cota,
-- emendas, contratos, licitações vencidas), sanções e alertas. O universo é `dim_empresa`.
with empresas as (
    select e.*, m.municipio_nome
    from {{ ref('dim_empresa') }} as e
    left join {{ ref('dim_municipio') }} as m on m.municipio_id = e.municipio_id
),

cota as (
    select
        c.fornecedor_cnpj_raiz as cnpj_raiz,
        sum(c.valor) as total,
        list(
            {'parlamentar_id': c.parlamentar_id, 'nome': p.nome, 'valor': c.valor}
            order by c.valor desc, c.parlamentar_id
        ) filter (where c.ordem <= {{ var('site_top') }}) as itens
    from (
        select
            fornecedor_cnpj_raiz,
            parlamentar_id,
            sum(valor) as valor,
            row_number() over (
                partition by fornecedor_cnpj_raiz order by sum(valor) desc, parlamentar_id
            ) as ordem
        from {{ ref('site_cota') }}
        where fornecedor_cnpj_raiz is not null
        group by fornecedor_cnpj_raiz, parlamentar_id
    ) as c
    left join {{ ref('dim_parlamentar') }} as p on p.parlamentar_id = c.parlamentar_id
    group by c.fornecedor_cnpj_raiz
),

emendas as (
    select
        favorecido_cnpj_raiz as cnpj_raiz,
        sum(pago) as total,
        list(
            {'autor': autor, 'parlamentar_id': parlamentar_id, 'pago': pago}
            order by pago desc, autor
        ) filter (where ordem <= {{ var('site_top') }}) as itens
    from (
        select
            favorecido_cnpj_raiz,
            max(autor_nome) as autor,
            max(parlamentar_id) as parlamentar_id,
            sum(pago) as pago,
            row_number() over (
                partition by favorecido_cnpj_raiz order by sum(pago) desc, max(autor_nome)
            ) as ordem
        from {{ ref('site_emendas') }}
        where favorecido_cnpj_raiz is not null
        group by favorecido_cnpj_raiz, autor_codigo
    )
    group by favorecido_cnpj_raiz
),

contratos as (
    select
        cnpj_raiz,
        sum(valor) as total,
        sum(contratos) as quantidade,
        list(
            {'orgao': orgao_nome, 'valor': valor, 'contratos': contratos}
            order by valor desc, orgao_nome
        ) filter (where ordem <= {{ var('site_top') }}) as itens
    from (
        select
            *,
            row_number() over (partition by cnpj_raiz order by valor desc, orgao_nome) as ordem
        from {{ ref('site_contratos') }}
    )
    group by cnpj_raiz
),

sancoes as (
    select
        sancionado_cnpj_raiz as cnpj_raiz,
        list(
            {
                'sancao_id': sancao_id, 'cadastro': cadastro, 'categoria': categoria,
                'orgao': orgao_sancionador, 'inicio': data_inicio, 'fim': data_fim,
                'vigente': data_fim is null or data_fim >= current_date
            }
            order by data_inicio desc nulls last, sancao_id
        ) as itens
    from {{ ref('fct_sancao') }}
    where sancionado_cnpj_raiz is not null
    group by sancionado_cnpj_raiz
),

-- o alerta de sócios em comum aparece no arquivo das duas empresas
alertas_por_empresa as (
    select cnpj_raiz as empresa, * from {{ ref('site_alertas') }} where cnpj_raiz is not null
    union all
    select cnpj_raiz_2 as empresa, * from {{ ref('site_alertas') }} where cnpj_raiz_2 is not null
),

alertas as (
    select
        empresa as cnpj_raiz,
        count(*) as total,
        list({{ site_alerta_json() }} order by {{ site_ordem_alertas() }})
            filter (where ordem <= {{ var('site_max_alertas') }}) as itens
    from (
        select
            *,
            row_number() over (partition by empresa order by {{ site_ordem_alertas() }}) as ordem
        from alertas_por_empresa
    )
    group by empresa
),

uma as (
    select
        e.cnpj_raiz,
        {
            'cadastro': {
                'razao_social': e.razao_social,
                'natureza_juridica': e.natureza_juridica,
                'porte': e.porte,
                'capital_social': e.capital_social,
                'abertura': e.data_abertura,
                'situacao': e.situacao,
                'data_situacao': e.data_situacao,
                'motivo_situacao': e.motivo_situacao,
                'atividade': e.cnae_principal_descricao,
                'municipio': e.municipio_nome,
                'uf': e.uf_sigla,
                'optante_simples': e.optante_simples,
                'optante_mei': e.optante_mei,
                'estabelecimentos': e.estabelecimentos,
                'socios': e.socios,
                'matriz_cnpj': e.matriz_cnpj,
                'url_portal': 'https://portaldatransparencia.gov.br/busca?termo=' || e.matriz_cnpj,
                'competencia_receita': e.competencia_receita
            },
            'cota': {'total': coalesce(c.total, 0), 'parlamentares': coalesce(c.itens, [])},
            'emendas': {'total_pago': coalesce(em.total, 0), 'autores': coalesce(em.itens, [])},
            'contratos': {
                'total': coalesce(k.total, 0),
                'quantidade': coalesce(k.quantidade, 0),
                'orgaos': coalesce(k.itens, [])
            },
            'licitacoes': {'vencidas': coalesce(l.vencidas, 0)},
            'sancoes': coalesce(s.itens, []),
            'alertas': {'total': coalesce(a.total, 0), 'itens': coalesce(a.itens, [])}
        } as dados,
        coalesce(a.total, 0) as alertas_total,
        coalesce(len(a.itens), 0) as alertas_no_arquivo
    from empresas as e
    left join cota as c on c.cnpj_raiz = e.cnpj_raiz
    left join emendas as em on em.cnpj_raiz = e.cnpj_raiz
    left join contratos as k on k.cnpj_raiz = e.cnpj_raiz
    left join {{ ref('site_licitacoes') }} as l on l.cnpj_raiz = e.cnpj_raiz
    left join sancoes as s on s.cnpj_raiz = e.cnpj_raiz
    left join alertas as a on a.cnpj_raiz = e.cnpj_raiz
)

select
    'empresa/b_' || left(cnpj_raiz, 3) || '.json' as caminho,
    to_json({
        'esquema': 1,
        'bloco': left(cnpj_raiz, 3),
        'empresas': map_from_entries(list((cnpj_raiz, dados) order by cnpj_raiz))
    })::varchar as conteudo,
    count(*) as empresas_no_arquivo,
    sum(alertas_total) as alertas_total,
    sum(alertas_no_arquivo) as alertas_no_arquivo
from uma
group by left(cnpj_raiz, 3)
