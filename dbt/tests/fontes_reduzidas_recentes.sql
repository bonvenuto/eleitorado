{{ config(severity='warn') }}

-- Fonte que publicou bem menos linhas nos últimos 7 dias: aviso no log, sem bloquear a publicação.
select recurso_id, competencia, coletada_em, linhas_antes, linhas_depois, variacao_pct
from {{ ref('alerta_fonte_reduzida') }}
where coletada_em >= current_timestamp - interval 7 day
