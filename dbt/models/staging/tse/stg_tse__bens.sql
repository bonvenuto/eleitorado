-- depends_on: {{ source('raw_tse', 'bens') }}
-- Camada privada: linha_original conserva todas as colunas fonte antes dos casts.
with tipado as (
    select
        {{ data_br('dt_geracao') }} as dt_geracao,
        hh_geracao::varchar as hh_geracao,
        nullif({{ texto('ano_eleicao') }}, '-4')::varchar as ano_eleicao,
        nullif({{ texto('cd_tipo_eleicao') }}, '-4')::varchar as cd_tipo_eleicao,
        nm_tipo_eleicao::varchar as nm_tipo_eleicao,
        nullif({{ texto('cd_eleicao') }}, '-4')::varchar as cd_eleicao,
        ds_eleicao::varchar as ds_eleicao,
        {{ data_br('dt_eleicao') }} as dt_eleicao,
        sg_uf::varchar as sg_uf,
        sg_ue::varchar as sg_ue,
        nm_ue::varchar as nm_ue,
        nullif({{ texto('sq_candidato') }}, '-4')::varchar as sq_candidato,
        nullif({{ texto('nr_ordem_bem_candidato') }}, '-4')::varchar as nr_ordem_bem_candidato,
        nullif({{ texto('cd_tipo_bem_candidato') }}, '-4')::varchar as cd_tipo_bem_candidato,
        ds_tipo_bem_candidato::varchar as ds_tipo_bem_candidato,
        ds_bem_candidato::varchar as ds_bem_candidato,
        {{ numero_br('vr_bem_candidato') }} as vr_bem_candidato,
        {{ data_br('dt_ult_atual_bem_candidato') }} as dt_ult_atual_bem_candidato,
        hh_ult_atual_bem_candidato::varchar as hh_ult_atual_bem_candidato,
        _coleta_id,
        _competencia,
        _competencia_data,
        _linha,
        _arquivo_original,
        _carregado_em,
        ano_arquivo,
        versao_id,
        layout_id,
        to_json(struct_pack(
            dt_geracao := dt_geracao,
            hh_geracao := hh_geracao,
            ano_eleicao := ano_eleicao,
            cd_tipo_eleicao := cd_tipo_eleicao,
            nm_tipo_eleicao := nm_tipo_eleicao,
            cd_eleicao := cd_eleicao,
            ds_eleicao := ds_eleicao,
            dt_eleicao := dt_eleicao,
            sg_uf := sg_uf,
            sg_ue := sg_ue,
            nm_ue := nm_ue,
            sq_candidato := sq_candidato,
            nr_ordem_bem_candidato := nr_ordem_bem_candidato,
            cd_tipo_bem_candidato := cd_tipo_bem_candidato,
            ds_tipo_bem_candidato := ds_tipo_bem_candidato,
            ds_bem_candidato := ds_bem_candidato,
            vr_bem_candidato := vr_bem_candidato,
            dt_ult_atual_bem_candidato := dt_ult_atual_bem_candidato,
            hh_ult_atual_bem_candidato := hh_ult_atual_bem_candidato
        )) as linha_original
    from {{ fonte_tse('bens') }}
)

select
    *,
    dt_eleicao as data_eleicao,
    'tse:' || cd_eleicao || ':' || sq_candidato as candidatura_id
from tipado
where year(dt_eleicao) in (2018, 2020, 2022, 2024)
