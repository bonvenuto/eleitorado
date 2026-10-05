-- CEAPS do Senado: um registro por despesa (`id` único). Números e datas ISO no JSON.
with origem as (
    select * from {{ source('raw_senado', 'ceaps') }}
)

select
    _coleta_id,
    _competencia,
    json_extract_string(payload, '$.id') as id_despesa,
    json_extract_string(payload, '$.codSenador') as id_senador,
    json_extract_string(payload, '$.nomeSenador') as nome_senador,
    try_cast(json_extract_string(payload, '$.ano') as bigint) as ano,
    try_cast(json_extract_string(payload, '$.mes') as bigint) as mes,
    json_extract_string(payload, '$.tipoDespesa') as categoria,
    json_extract_string(payload, '$.tipoDocumento') as tipo_documento_fiscal,
    -- CPF de pessoa física às vezes já vem mascarado pelo Senado (`240.***.***-04`)
    if(
        contains(json_extract_string(payload, '$.cpfCnpj'), '*'),
        null,
        {{ normalizar_documento("json_extract_string(payload, '$.cpfCnpj')") }}
    ) as fornecedor_documento,
    if(
        contains(json_extract_string(payload, '$.cpfCnpj'), '*'),
        trim(json_extract_string(payload, '$.cpfCnpj')),
        null
    ) as fornecedor_documento_mascarado,
    json_extract_string(payload, '$.fornecedor') as fornecedor_nome,
    json_extract_string(payload, '$.documento') as numero_documento,
    try_cast(json_extract_string(payload, '$.data') as date) as data_emissao,
    json_extract_string(payload, '$.detalhamento') as detalhamento,
    {{ numero("json_extract_string(payload, '$.valorReembolsado')") }} as valor_reembolsado
from origem
