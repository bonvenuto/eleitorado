-- Registro de cada coleta (uma linha por coleta), gravado pelo coletor em meta/coletas.
select
    coleta_id,
    orgao,
    recurso,
    concat(orgao, '.', recurso) as recurso_id,
    competencia,
    destino,
    status,
    iniciada_em,
    finalizada_em,
    linhas,
    esquema_alterado
from {{ source('meta', 'coletas') }}
