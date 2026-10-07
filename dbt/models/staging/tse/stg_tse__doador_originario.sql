-- depends_on: {{ source('raw_tse', 'doador_originario') }}
-- Camada privada: linha_original conserva todas as colunas fonte antes dos casts.
with tipado as (
    select
        {{ data_br('dt_geracao') }} as dt_geracao,
        hh_geracao::varchar as hh_geracao,
        nullif({{ texto('aa_eleicao') }}, '-4')::varchar as aa_eleicao,
        nullif({{ texto('cd_tipo_eleicao') }}, '-4')::varchar as cd_tipo_eleicao,
        nm_tipo_eleicao::varchar as nm_tipo_eleicao,
        nullif({{ texto('cd_eleicao') }}, '-4')::varchar as cd_eleicao,
        ds_eleicao::varchar as ds_eleicao,
        {{ data_br('dt_eleicao') }} as dt_eleicao,
        st_turno::varchar as st_turno,
        tp_prestacao_contas::varchar as tp_prestacao_contas,
        {{ data_br('dt_prestacao_contas') }} as dt_prestacao_contas,
        nullif({{ texto('sq_prestador_contas') }}, '-4')::varchar as sq_prestador_contas,
        sg_uf::varchar as sg_uf,
        {{ documento_fonte("nullif(trim(nr_cpf_cnpj_doador_originario), '-4')") }}
            as nr_cpf_cnpj_doador_originario,
        nm_doador_originario::varchar as nm_doador_originario,
        nm_doador_originario_rfb::varchar as nm_doador_originario_rfb,
        tp_doador_originario::varchar as tp_doador_originario,
        nullif({{ texto('cd_cnae_doador_originario') }}, '-4')::varchar
            as cd_cnae_doador_originario,
        ds_cnae_doador_originario::varchar as ds_cnae_doador_originario,
        nullif({{ texto('sq_receita') }}, '-4')::varchar as sq_receita,
        {{ data_br('dt_receita') }} as dt_receita,
        ds_receita::varchar as ds_receita,
        {{ numero_br('vr_receita') }} as vr_receita,
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
            aa_eleicao := aa_eleicao,
            cd_tipo_eleicao := cd_tipo_eleicao,
            nm_tipo_eleicao := nm_tipo_eleicao,
            cd_eleicao := cd_eleicao,
            ds_eleicao := ds_eleicao,
            dt_eleicao := dt_eleicao,
            st_turno := st_turno,
            tp_prestacao_contas := tp_prestacao_contas,
            dt_prestacao_contas := dt_prestacao_contas,
            sq_prestador_contas := sq_prestador_contas,
            sg_uf := sg_uf,
            nr_cpf_cnpj_doador_originario := nr_cpf_cnpj_doador_originario,
            nm_doador_originario := nm_doador_originario,
            nm_doador_originario_rfb := nm_doador_originario_rfb,
            tp_doador_originario := tp_doador_originario,
            cd_cnae_doador_originario := cd_cnae_doador_originario,
            ds_cnae_doador_originario := ds_cnae_doador_originario,
            sq_receita := sq_receita,
            dt_receita := dt_receita,
            ds_receita := ds_receita,
            vr_receita := vr_receita
        )) as linha_original,
        case
            when trim(nr_cpf_cnpj_doador_originario) = '-4' then 'sentinela_menos4'
            when nullif(trim(nr_cpf_cnpj_doador_originario), '') is null then 'nao_informado'
            when regexp_matches(trim(nr_cpf_cnpj_doador_originario), '^-[0-9]+$') then 'codigo_negativo'
        end::varchar as nr_cpf_cnpj_doador_originario_ausencia
    from {{ fonte_tse('doador_originario') }}
)

select
    *,
    dt_eleicao as data_eleicao,
    tp_prestacao_contas as tipo_prestacao,
    dt_prestacao_contas as data_prestacao,
    {{ documento_valido('nr_cpf_cnpj_doador_originario') }} as nr_cpf_cnpj_doador_originario_valido
from tipado
where year(dt_eleicao) in (2018, 2020, 2022, 2024)
