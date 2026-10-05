-- Situação de cada recurso: última coleta, último sucesso e atraso em relação à cadência.
-- Base dos testes de atraso (seção 7.7 da spec), que substituem o `dbt source freshness`.
with coletas as (
    select
        recurso_id,
        iniciada_em,
        finalizada_em,
        status,
        linhas,
        esquema_alterado
    from {{ ref('stg_meta__coletas') }}
    where destino = 'raw'
),

resumo as (
    select
        recurso_id,
        max(iniciada_em) as ultima_coleta,
        max(if(status in ('carregada', 'sem_alteracao'), finalizada_em, null)) as ultimo_sucesso,
        arg_max(status, iniciada_em) as status_ultima_coleta,
        arg_max(linhas, iniciada_em) filter (where status = 'carregada') as linhas_ultima_carga,
        count_if(esquema_alterado and iniciada_em >= current_timestamp - interval 30 day)
            as mudancas_esquema_30d
    from coletas
    group by recurso_id
)

select
    f.recurso_id,
    f.cadencia_corrente,
    r.ultima_coleta,
    r.ultimo_sucesso,
    r.status_ultima_coleta,
    r.linhas_ultima_carga,
    coalesce(r.mudancas_esquema_30d, 0) as mudancas_esquema_30d,
    date_diff('hour', r.ultimo_sucesso, current_timestamp) as atraso_horas,
    case f.cadencia_corrente when 'diaria' then 30 when 'semanal' then 192 else 840 end
        as limite_aviso_horas,
    case f.cadencia_corrente when 'diaria' then 54 when 'semanal' then 240 else 960 end
        as limite_erro_horas
from {{ ref('stg_meta__fontes') }} as f
left join resumo as r
    on r.recurso_id = f.recurso_id
