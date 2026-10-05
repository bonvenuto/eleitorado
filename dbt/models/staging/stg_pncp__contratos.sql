-- Contratos do PNCP (todas as esferas): os publicados por dia e as atualizações recentes.
-- Uma linha por versão coletada; a vigente é escolhida em int_pncp__contratos.
with origem as (
    select _coleta_id, payload, 'publicacao' as origem from {{ source('raw_pncp', 'contratos') }}
    union all
    select _coleta_id, payload, 'atualizacao' as origem from {{ source('raw_pncp', 'contratos_atualizacao') }}
)

select
    _coleta_id,
    origem,
    json_extract_string(payload, '$.numeroControlePNCP') as contrato_pncp_id,
    json_extract_string(payload, '$.numeroControlePncpCompra') as compra_pncp_id,
    json_extract_string(payload, '$.orgaoEntidade.cnpj') as orgao_cnpj,
    json_extract_string(payload, '$.orgaoEntidade.razaoSocial') as orgao_nome,
    json_extract_string(payload, '$.orgaoEntidade.esferaId') as esfera,
    json_extract_string(payload, '$.orgaoEntidade.poderId') as poder,
    json_extract_string(payload, '$.unidadeOrgao.codigoUnidade') as unidade_codigo,
    json_extract_string(payload, '$.unidadeOrgao.nomeUnidade') as unidade_nome,
    json_extract_string(payload, '$.unidadeOrgao.ufSigla') as uf_sigla,
    json_extract_string(payload, '$.unidadeOrgao.codigoIbge') as municipio_id,
    try_cast(json_extract_string(payload, '$.anoContrato') as integer) as ano_contrato,
    json_extract_string(payload, '$.numeroContratoEmpenho') as numero_contrato,
    json_extract_string(payload, '$.processo') as processo,
    json_extract_string(payload, '$.tipoContrato.nome') as tipo_contrato,
    json_extract_string(payload, '$.categoriaProcesso.nome') as categoria_processo,
    json_extract_string(payload, '$.objetoContrato') as objeto,
    {{ documento_fonte("json_extract_string(payload, '$.niFornecedor')") }} as fornecedor_documento,
    {{ tipo_documento_fonte("json_extract_string(payload, '$.niFornecedor')") }} as fornecedor_tipo_documento,
    json_extract_string(payload, '$.nomeRazaoSocialFornecedor') as fornecedor_nome,
    {{ numero("json_extract_string(payload, '$.valorInicial')") }} as valor_inicial,
    {{ numero("json_extract_string(payload, '$.valorGlobal')") }} as valor_global,
    {{ numero("json_extract_string(payload, '$.valorAcumulado')") }} as valor_acumulado,
    try_cast(json_extract_string(payload, '$.dataAssinatura') as date) as data_assinatura,
    try_cast(json_extract_string(payload, '$.dataVigenciaInicio') as date) as data_inicio_vigencia,
    try_cast(json_extract_string(payload, '$.dataVigenciaFim') as date) as data_fim_vigencia,
    try_cast(json_extract_string(payload, '$.dataPublicacaoPncp') as timestamp) as data_publicacao,
    try_cast(json_extract_string(payload, '$.dataAtualizacaoGlobal') as timestamp) as data_atualizacao,
    try_cast(json_extract_string(payload, '$.numeroRetificacao') as integer) as numero_retificacao,
    json_extract_string(payload, '$.emendaParlamentar') as emenda_parlamentar
from origem
