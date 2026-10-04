-- Deputados por legislatura, em todas as datas de referência do raw (ou do replay).
with origem as (
    select * from {{ fonte_snapshot('camara', 'deputados') }}
)

select
    _coleta_id,
    _competencia_data as data_referencia,
    json_value(payload, '$.id') as id_deputado,
    json_value(payload, '$.nome') as nome,
    json_value(payload, '$.siglaPartido') as partido_sigla,
    json_value(payload, '$.siglaUf') as uf_sigla,
    safe_cast(json_value(payload, '$.idLegislatura') as int64) as legislatura,
    json_value(payload, '$.urlFoto') as url_foto
from origem
