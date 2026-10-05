-- Carga com pelo menos 10% menos linhas que a carga anterior: a fonte encolheu (ou foi
-- reprocessada). Recursos por competência comparam a mesma competência; snapshots comparam com o
-- snapshot anterior do recurso. É um indício para investigar: os originais das duas versões
-- ficam arquivados no bucket.
with cargas as (
    select
        c.coleta_id,
        c.recurso_id,
        c.competencia,
        c.finalizada_em,
        c.linhas,
        if(f.publicacao = 'snapshot', c.recurso_id, concat(c.recurso_id, '|', c.competencia))
            as serie
    from {{ ref('stg_meta__coletas') }} as c
    left join {{ ref('stg_meta__fontes') }} as f
        on f.recurso_id = c.recurso_id
    where c.destino = 'raw' and c.status = 'carregada' and c.linhas is not null
),

comparadas as (
    select
        *,
        lag(linhas) over janela as linhas_antes,
        lag(coleta_id) over janela as coleta_id_antes
    from cargas
    window janela as (partition by serie order by finalizada_em)
)

select
    md5(concat('fonte_reduzida|', coleta_id)) as alerta_id,
    recurso_id,
    competencia,
    coleta_id,
    coleta_id_antes,
    finalizada_em as coletada_em,
    linhas_antes,
    linhas as linhas_depois,
    round(100.0 * (linhas - linhas_antes) / linhas_antes, 1) as variacao_pct,
    'Carga com pelo menos 10% menos linhas que a carga anterior da mesma série' as regra
from comparadas
where linhas_antes > 0 and linhas <= 0.9 * linhas_antes
