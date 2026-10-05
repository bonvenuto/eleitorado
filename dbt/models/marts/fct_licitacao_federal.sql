-- Licitações do Poder Executivo federal (2013 a 2024-04), na versão mais recente.
select
    concat('cgu:', ug_codigo, ':', modalidade_codigo, ':', licitacao_numero) as licitacao_id,
    licitacao_numero,
    ug_codigo,
    {{ mascarar_cpfs_em_texto('ug_nome') }} as ug_nome,
    modalidade_codigo,
    modalidade,
    numero_processo,
    {{ mascarar_cpfs_em_texto('objeto') }} as objeto,
    situacao,
    orgao_superior_codigo,
    orgao_superior_nome,
    orgao_codigo,
    orgao_nome,
    uf_sigla,
    municipio_nome,
    data_abertura,
    data_resultado,
    valor,
    _competencia as competencia_publicacao,
    _coleta_id
from {{ ref('stg_cgu__licitacoes') }}
where ug_codigo is not null and licitacao_numero is not null
qualify row_number() over (
    partition by ug_codigo, modalidade_codigo, licitacao_numero
    order by _competencia_data desc, _coleta_id desc
) = 1
