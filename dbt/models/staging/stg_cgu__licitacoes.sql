-- Licitações do Poder Executivo federal (2013 a 2024-04), um arquivo por mês.
select
    _coleta_id,
    _competencia,
    _competencia_data,
    {{ texto('numero_licitacao') }} as licitacao_numero,
    {{ texto('codigo_ug') }} as ug_codigo,
    {{ texto('nome_ug') }} as ug_nome,
    {{ texto('codigo_modalidade_compra') }} as modalidade_codigo,
    {{ texto('modalidade_compra') }} as modalidade,
    {{ texto('numero_processo') }} as numero_processo,
    {{ texto('objeto') }} as objeto,
    {{ texto('situacao_licitacao') }} as situacao,
    {{ texto('codigo_orgao_superior') }} as orgao_superior_codigo,
    {{ texto('nome_orgao_superior') }} as orgao_superior_nome,
    {{ texto('codigo_orgao') }} as orgao_codigo,
    {{ texto('nome_orgao') }} as orgao_nome,
    {{ texto('uf') }} as uf_sigla,
    {{ texto('municipio') }} as municipio_nome,
    {{ data_br('data_resultado_compra') }} as data_resultado,
    {{ data_br('data_abertura') }} as data_abertura,
    {{ numero_br('valor_licitacao') }} as valor
from {{ source('raw_cgu', 'licitacoes') }}
