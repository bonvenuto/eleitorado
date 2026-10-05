-- Emendas parlamentares do snapshot mais recente (Portal da Transparência). Uma linha por linha
-- publicada; nas emendas antigas o código vem como "Sem informação".
with origem as (
    select * from {{ source('raw_cgu', 'emendas') }}
    where _competencia_data = (select max(_competencia_data) from {{ source('raw_cgu', 'emendas') }})
)

select
    _coleta_id,
    _competencia_data as data_referencia,
    if(regexp_matches(coalesce({{ texto('codigo_da_emenda') }}, ''), '^[0-9]+$'), {{ texto('codigo_da_emenda') }}, null)
        as emenda_codigo,
    try_cast({{ texto('ano_da_emenda') }} as integer) as ano,
    {{ texto('tipo_de_emenda') }} as tipo_emenda,
    nullif({{ texto('codigo_do_autor_da_emenda') }}, 'S/I') as autor_codigo,
    nullif({{ texto('nome_do_autor_da_emenda') }}, 'Sem informação') as autor_nome,
    nullif({{ texto('numero_da_emenda') }}, 'S/I') as numero_emenda,
    {{ texto('localidade_de_aplicacao_do_recurso') }} as localidade,
    if(regexp_matches(coalesce({{ texto('codigo_municipio_ibge') }}, ''), '^[0-9]{7}$'), {{ texto('codigo_municipio_ibge') }}, null)
        as municipio_id,
    {{ texto('municipio') }} as municipio_nome,
    if(regexp_matches(coalesce({{ texto('codigo_uf_ibge') }}, ''), '^[0-9]{7}$'), substr({{ texto('codigo_uf_ibge') }}, 1, 2), null)
        as uf_id,
    {{ texto('regiao') }} as regiao,
    {{ texto('codigo_funcao') }} as funcao_codigo,
    {{ texto('nome_funcao') }} as funcao,
    {{ texto('codigo_subfuncao') }} as subfuncao_codigo,
    {{ texto('nome_subfuncao') }} as subfuncao,
    {{ texto('codigo_programa') }} as programa_codigo,
    {{ texto('nome_programa') }} as programa,
    {{ texto('codigo_acao') }} as acao_codigo,
    {{ texto('nome_acao') }} as acao,
    {{ numero_br('valor_empenhado') }} as valor_empenhado,
    {{ numero_br('valor_liquidado') }} as valor_liquidado,
    {{ numero_br('valor_pago') }} as valor_pago,
    {{ numero_br('valor_restos_a_pagar_inscritos') }} as valor_restos_a_pagar_inscritos,
    {{ numero_br('valor_restos_a_pagar_cancelados') }} as valor_restos_a_pagar_cancelados,
    {{ numero_br('valor_restos_a_pagar_pagos') }} as valor_restos_a_pagar_pagos,
    md5(to_json(struct_pack(*columns(* exclude (
        _coleta_id, _competencia, _competencia_data, _linha, _arquivo_original, _carregado_em
    ))))) as hash_linha
from origem
