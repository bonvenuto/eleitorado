-- Municípios do snapshot mais recente. A UF vem da região imediata, que todos têm;
-- micro e mesorregião podem faltar em municípios novos.
with origem as (
    select * from {{ source('raw_ibge', 'municipios') }}
    where _competencia_data = (
        select max(_competencia_data) from {{ source('raw_ibge', 'municipios') }}
    )
)

select
    _coleta_id,
    json_extract_string(payload, '$.id') as municipio_id,
    json_extract_string(payload, '$.nome') as municipio_nome,
    json_extract_string(payload, '$."regiao-imediata"."regiao-intermediaria".UF.id') as uf_id,
    json_extract_string(payload, '$."regiao-imediata"."regiao-intermediaria".UF.sigla') as uf_sigla,
    json_extract_string(payload, '$."regiao-imediata"."regiao-intermediaria".UF.nome') as uf_nome,
    json_extract_string(payload, '$."regiao-imediata"."regiao-intermediaria".UF.regiao.sigla') as regiao_sigla,
    json_extract_string(payload, '$."regiao-imediata"."regiao-intermediaria".UF.regiao.nome') as regiao_nome,
    json_extract_string(payload, '$.microrregiao.nome') as microrregiao,
    json_extract_string(payload, '$.microrregiao.mesorregiao.nome') as mesorregiao,
    json_extract_string(payload, '$."regiao-imediata".nome') as regiao_imediata,
    json_extract_string(payload, '$."regiao-imediata"."regiao-intermediaria".nome') as regiao_intermediaria
from origem
