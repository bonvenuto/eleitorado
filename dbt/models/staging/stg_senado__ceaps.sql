-- CEAPS do Senado: um registro por despesa (`id` único). Números e datas ISO no JSON.
with origem as (
    select * from {{ source('raw_senado', 'ceaps') }}
)

select
    _coleta_id,
    _competencia,
    json_value(payload, '$.id') as id_despesa,
    json_value(payload, '$.codSenador') as id_senador,
    json_value(payload, '$.nomeSenador') as nome_senador,
    safe_cast(json_value(payload, '$.ano') as int64) as ano,
    safe_cast(json_value(payload, '$.mes') as int64) as mes,
    json_value(payload, '$.tipoDespesa') as categoria,
    json_value(payload, '$.tipoDocumento') as tipo_documento_fiscal,
    -- CPF de pessoa física às vezes já vem mascarado pelo Senado (`240.***.***-04`)
    if(
        contains_substr(json_value(payload, '$.cpfCnpj'), '*'),
        null,
        {{ normalizar_documento("json_value(payload, '$.cpfCnpj')") }}
    ) as fornecedor_documento,
    if(
        contains_substr(json_value(payload, '$.cpfCnpj'), '*'),
        trim(json_value(payload, '$.cpfCnpj')),
        null
    ) as fornecedor_documento_mascarado,
    json_value(payload, '$.fornecedor') as fornecedor_nome,
    json_value(payload, '$.documento') as numero_documento,
    safe_cast(json_value(payload, '$.data') as date) as data_emissao,
    json_value(payload, '$.detalhamento') as detalhamento,
    safe_cast(json_value(payload, '$.valorReembolsado') as numeric) as valor_reembolsado
from origem
