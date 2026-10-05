-- Favorecidos de emendas por mês (snapshot mais recente). O CPF já vem mascarado pela fonte.
with origem as (
    select * from {{ source('raw_cgu', 'emendas_favorecidos') }}
    where _competencia_data = (select max(_competencia_data) from {{ source('raw_cgu', 'emendas_favorecidos') }})
)

select
    _coleta_id,
    _competencia_data as data_referencia,
    if(regexp_matches(coalesce({{ texto('codigo_da_emenda') }}, ''), '^[0-9]+$'), {{ texto('codigo_da_emenda') }}, null)
        as emenda_codigo,
    nullif({{ texto('codigo_do_autor_da_emenda') }}, 'S/I') as autor_codigo,
    nullif({{ texto('nome_do_autor_da_emenda') }}, 'Sem informação') as autor_nome,
    nullif({{ texto('numero_da_emenda') }}, 'S/I') as numero_emenda,
    {{ texto('tipo_de_emenda') }} as tipo_emenda,
    try_strptime({{ texto('ano_mes') }}, '%Y%m')::date as mes_referencia,
    {{ documento_fonte('codigo_do_favorecido') }} as favorecido_documento,
    {{ tipo_documento_fonte('codigo_do_favorecido') }} as favorecido_tipo_documento,
    {{ texto('favorecido') }} as favorecido_nome,
    {{ texto('natureza_juridica') }} as natureza_juridica,
    {{ texto('tipo_favorecido') }} as tipo_favorecido,
    {{ texto('uf_favorecido') }} as favorecido_uf,
    {{ texto('municipio_favorecido') }} as favorecido_municipio,
    {{ numero_br('valor_recebido') }} as valor_recebido,
    md5(to_json(struct_pack(*columns(* exclude (
        _coleta_id, _competencia, _competencia_data, _linha, _arquivo_original, _carregado_em
    ))))) as hash_linha
from origem
