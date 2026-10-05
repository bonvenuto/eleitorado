-- Contratos do Poder Executivo federal, um arquivo por mês de publicação. O mesmo contrato pode
-- reaparecer em meses diferentes; a versão vigente é escolhida no intermediate.
select
    _coleta_id,
    _competencia,
    _competencia_data,
    {{ texto('numero_do_contrato') }} as contrato_numero,
    {{ texto('objeto') }} as objeto,
    {{ texto('fundamento_legal') }} as fundamento_legal,
    {{ texto('modalidade_compra') }} as modalidade,
    {{ texto('situacao_contrato') }} as situacao,
    {{ texto('codigo_orgao_superior') }} as orgao_superior_codigo,
    {{ texto('nome_orgao_superior') }} as orgao_superior_nome,
    {{ texto('codigo_orgao') }} as orgao_codigo,
    {{ texto('nome_orgao') }} as orgao_nome,
    {{ texto('codigo_ug') }} as ug_codigo,
    {{ texto('nome_ug') }} as ug_nome,
    {{ data_br('data_assinatura_contrato') }} as data_assinatura,
    {{ data_br('data_publicacao_dou') }} as data_publicacao,
    {{ data_br('data_inicio_vigencia') }} as data_inicio_vigencia,
    {{ data_br('data_fim_vigencia') }} as data_fim_vigencia,
    {{ documento_fonte('codigo_contratado') }} as fornecedor_documento,
    {{ tipo_documento_fonte('codigo_contratado') }} as fornecedor_tipo_documento,
    {{ texto('nome_contratado') }} as fornecedor_nome,
    {{ numero_br('valor_inicial_compra') }} as valor_inicial,
    {{ numero_br('valor_final_compra') }} as valor_final,
    if(regexp_matches(coalesce({{ texto('numero_licitacao') }}, ''), '^-[0-9]+$'), null, {{ texto('numero_licitacao') }})
        as licitacao_numero,
    {{ texto('codigo_ug_licitacao') }} as licitacao_ug_codigo,
    {{ texto('codigo_modalidade_compra_licitacao') }} as licitacao_modalidade_codigo
from {{ source('raw_cgu', 'contratos') }}
