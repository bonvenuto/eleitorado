-- Privado. Política v1: igualdade integral de linha_original, mesma parcela e origem.
-- A identidade estável de negócio NÃO decide igualdade: geração e léxico entram no JSON fonte.
-- Divergências, chaves incompletas e gate bloqueado preservam todas as ocorrências privadas.
{% set parcela = 'cd_eleicao, sq_prestador_contas, sq_despesa, tipo_prestacao,
    data_prestacao, sq_parcelamento_despesa, ano_arquivo, versao_id' %}
with identificados as (
    select s.*,
        md5(to_json(list_value('pagamentos', cd_eleicao, sq_prestador_contas, sq_despesa,
            tipo_prestacao, cast(data_prestacao as varchar), sq_parcelamento_despesa))) as fato_id,
        {{ tse_linha_id('pagamentos', ['cd_eleicao', 'sq_prestador_contas', 'sq_despesa',
            'tipo_prestacao', 'data_prestacao', 'sq_parcelamento_despesa'], [
            'aa_eleicao',
            'cd_tipo_eleicao',
            'nm_tipo_eleicao',
            'cd_eleicao',
            'ds_eleicao',
            'dt_eleicao',
            'st_turno',
            'tp_prestacao_contas',
            'dt_prestacao_contas',
            'sq_prestador_contas',
            'sg_uf',
            'ds_tipo_documento',
            'nr_documento',
            'cd_fonte_despesa',
            'ds_fonte_despesa',
            'cd_origem_despesa',
            'ds_origem_despesa',
            'cd_natureza_despesa',
            'ds_natureza_despesa',
            'cd_especie_recurso',
            'ds_especie_recurso',
            'sq_despesa',
            'sq_parcelamento_despesa',
            'dt_pagto_despesa',
            'ds_despesa',
            'vr_pagto_despesa',
        ]) }} as item_id
    from {{ ref('stg_tse__pagamentos') }} s
), grupos as (
    select *,
        cast(regexp_extract(item_id, '-([0-9]+)$', 1) as bigint) as item_ocorrencia,
        count(*) over (partition by {{ parcela }}) as linhas_parcela,
        count(distinct struct_pack(original := linha_original)) over (
            partition by {{ parcela }}) > 1 as parcela_divergente,
        row_number() over (partition by {{ parcela }} order by item_id) as ocorrencia_parcela,
        list(struct_pack(coleta_id := _coleta_id, competencia := _competencia,
            competencia_data := _competencia_data, linha := _linha,
            arquivo_original := _arquivo_original, carregado_em := _carregado_em,
            ano_arquivo := ano_arquivo, versao_id := versao_id, layout_id := layout_id,
            item_id := item_id)) over (partition by {{ parcela }}) as origens_parcela_privadas,
        cd_eleicao is not null and sq_prestador_contas is not null and sq_despesa is not null
            and tipo_prestacao is not null and data_prestacao is not null
            and sq_parcelamento_despesa is not null and ano_arquivo is not null
            and versao_id is not null as chave_completa
    from identificados
), relacionados as (
    select g.*,
        g.vr_pagto_despesa::decimal(38,2) as valor,
        g.dt_pagto_despesa as data,
        m.candidatura_id, m.sq_candidato, m.fornecedor_documento, m.fornecedor_documento_valido,
        coalesce(m.mapa_elegivel, false) as mapa_elegivel,
        coalesce(m.candidatura_elegivel, false) as candidatura_elegivel,
        coalesce(p.prestacao_ambigua, true) as prestacao_ambigua,
        coalesce(p.origem_ambigua, true) as origem_ambigua,
        coalesce(p.metadados_incompletos, true) as metadados_incompletos,
        coalesce(p.prestacao_elegivel, false) as prestacao_elegivel,
        chave_completa and not parcela_divergente and linha_original is not null
            and coalesce(p.prestacao_elegivel, false) as colapso_autorizado
    from grupos g
    left join {{ ref('int_tse__mapa_despesas') }} m
        on g.cd_eleicao = m.cd_eleicao and g.sq_prestador_contas = m.sq_prestador_contas
        and g.sq_despesa = m.sq_despesa and g.tipo_prestacao = m.tipo_prestacao
        and g.data_prestacao = m.data_prestacao
    left join {{ ref('int_tse__prestacoes') }} p
        on g.cd_eleicao = p.cd_eleicao and g.sq_prestador_contas = p.sq_prestador_contas
), classificados as (
    select *,
        colapso_autorizado and mapa_elegivel as fato_elegivel,
        case
            when not chave_completa then 'chave_incompleta'
            when not prestacao_elegivel then 'prestacao_ou_origem_bloqueada'
            when linha_original is null then 'representacao_original_ausente'
            when parcela_divergente then 'parcela_divergente'
            when not mapa_elegivel then 'mapa_ausente_ou_inelegivel'
        end as motivo_pendencia,
        case when colapso_autorizado then linhas_parcela else 1::bigint end
            as quantidade_originais,
        'tse_pagamentos_identicos_v1'::varchar as politica_versao
    from relacionados
)
select *
from classificados
where not colapso_autorizado or ocorrencia_parcela = 1
