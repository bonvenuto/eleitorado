-- `resumo.json` (spec do site, seção 4.2): números da capa, tipos de alerta com o texto do seed e a
-- quantidade, os 20 alertas mais recentes de correspondência forte, a situação das fontes e as
-- fontes que encolheram. É o único arquivo com `gerado_em`.
with tipos as (
    select
        t.tipo,
        t.titulo,
        t.explicacao,
        t.cautela,
        t.ordem,
        count(a.alerta_id) as quantidade
    from {{ ref('site_alerta_tipos') }} as t
    left join {{ ref('site_alertas') }} as a on a.tipo = t.tipo
    group by t.tipo, t.titulo, t.explicacao, t.cautela, t.ordem
),

recentes as (
    select *
    from {{ ref('site_alertas') }}
    where correspondencia = 'forte' and data_fato <= current_date
    order by {{ site_ordem_alertas() }}
    limit 20
)

select
    'resumo.json' as caminho,
    to_json({
        'esquema': 1,
        'gerado_em': {{ site_instante('now()') }},
        'dados_ate': {
            'cota': (select max(data_competencia) from {{ ref('fct_despesa_cota_parlamentar') }}),
            'emendas': (
                select max(data_documento) from {{ ref('fct_emenda_pagamento') }}
                where data_documento <= current_date
            ),
            'contratos': (
                select max(data_assinatura) from {{ ref('fct_contrato_federal') }}
                where data_assinatura <= current_date
            ),
            'receita': (select max(competencia_receita) from {{ ref('dim_empresa') }})
        },
        'totais': {
            'cota': (select coalesce(sum(valor), 0) from {{ ref('site_cota') }}),
            'emendas_pago': (select coalesce(sum(pago), 0) from {{ ref('site_emendas') }}),
            'contratos': (select coalesce(sum(valor), 0) from {{ ref('site_contratos') }}),
            'parlamentares': (select count(*) from {{ ref('dim_parlamentar') }}),
            'empresas': (select count(*) from {{ ref('dim_empresa') }})
        },
        'alerta_tipos': (
            select coalesce(
                list(
                    {
                        'tipo': tipo, 'titulo': titulo, 'explicacao': explicacao,
                        'cautela': cautela, 'ordem': ordem, 'quantidade': quantidade
                    }
                    order by ordem
                ),
                []
            )
            from tipos
        ),
        'alertas_recentes': (
            select coalesce(list({{ site_alerta_json() }} order by {{ site_ordem_alertas() }}), [])
            from recentes
        ),
        'fontes': (
            select coalesce(
                list(
                    {
                        'recurso_id': recurso_id,
                        'cadencia': cadencia_corrente,
                        'ultimo_sucesso': {{ site_instante('ultimo_sucesso') }},
                        'status': status_ultima_coleta,
                        'atraso_horas': atraso_horas,
                        'situacao': case
                            when atraso_horas is null or atraso_horas >= limite_erro_horas
                                then 'erro'
                            when atraso_horas >= limite_aviso_horas then 'aviso'
                            else 'ok'
                        end
                    }
                    order by recurso_id
                ),
                []
            )
            from {{ ref('monitor_fontes') }}
        ),
        'fontes_reduzidas': (
            select coalesce(
                list(
                    {
                        'recurso_id': recurso_id,
                        'competencia': competencia,
                        'coletada_em': {{ site_instante('coletada_em') }},
                        'linhas_antes': linhas_antes,
                        'linhas_depois': linhas_depois,
                        'variacao_pct': variacao_pct
                    }
                    order by coletada_em desc, recurso_id
                ),
                []
            )
            from {{ ref('alerta_fonte_reduzida') }}
        )
    })::varchar as conteudo
