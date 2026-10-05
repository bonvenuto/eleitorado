-- Deputados por legislatura, em todas as datas de referência do raw (ou do replay).
with origem as (
    select * from {{ fonte_snapshot('camara', 'deputados') }}
)

select
    _coleta_id,
    _competencia_data as data_referencia,
    json_extract_string(payload, '$.id') as id_deputado,
    json_extract_string(payload, '$.nome') as nome,
    json_extract_string(payload, '$.siglaPartido') as partido_sigla,
    json_extract_string(payload, '$.siglaUf') as uf_sigla,
    try_cast(json_extract_string(payload, '$.idLegislatura') as bigint) as legislatura,
    json_extract_string(payload, '$.urlFoto') as url_foto
from origem
