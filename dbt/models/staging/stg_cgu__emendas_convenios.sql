-- Convênios ligados a emendas (snapshot mais recente). Só staging nesta onda.
with origem as (
    select * from {{ source('raw_cgu', 'emendas_convenios') }}
    where _competencia_data = (select max(_competencia_data) from {{ source('raw_cgu', 'emendas_convenios') }})
)

select
    _coleta_id,
    _competencia_data as data_referencia,
    {{ texto('codigo_da_emenda') }} as emenda_codigo,
    {{ texto('codigo_funcao') }} as funcao_codigo,
    {{ texto('nome_funcao') }} as funcao,
    {{ texto('codigo_subfuncao') }} as subfuncao_codigo,
    {{ texto('nome_subfuncao') }} as subfuncao,
    {{ texto('localidade_do_gasto') }} as localidade,
    {{ texto('tipo_de_emenda') }} as tipo_emenda,
    {{ data_br('data_publicacao_convenio') }} as data_publicacao,
    {{ texto('convenente') }} as convenente,
    {{ texto('objeto_convenio') }} as objeto,
    {{ texto('numero_convenio') }} as numero_convenio,
    {{ numero_br('valor_convenio') }} as valor_convenio
from origem
