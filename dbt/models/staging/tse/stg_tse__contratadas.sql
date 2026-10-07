-- depends_on: {{ source('raw_tse', 'contratadas') }}
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
        sg_ue::varchar as sg_ue,
        nm_ue::varchar as nm_ue,
        {{ documento_fonte("nullif(trim(nr_cnpj_prestador_conta), '-4')") }}
            as nr_cnpj_prestador_conta,
        nullif({{ texto('cd_cargo') }}, '-4')::varchar as cd_cargo,
        ds_cargo::varchar as ds_cargo,
        nullif({{ texto('sq_candidato') }}, '-4')::varchar as sq_candidato,
        nullif({{ texto('nr_candidato') }}, '-4')::varchar as nr_candidato,
        nm_candidato::varchar as nm_candidato,
        {{ documento_fonte("nullif(trim(nr_cpf_candidato), '-4')") }} as nr_cpf_candidato,
        {{ documento_fonte("nullif(trim(nr_cpf_vice_candidato), '-4')") }} as nr_cpf_vice_candidato,
        nullif({{ texto('nr_partido') }}, '-4')::varchar as nr_partido,
        sg_partido::varchar as sg_partido,
        nm_partido::varchar as nm_partido,
        nullif({{ texto('cd_tipo_fornecedor') }}, '-4')::varchar as cd_tipo_fornecedor,
        ds_tipo_fornecedor::varchar as ds_tipo_fornecedor,
        nullif({{ texto('cd_cnae_fornecedor') }}, '-4')::varchar as cd_cnae_fornecedor,
        ds_cnae_fornecedor::varchar as ds_cnae_fornecedor,
        {{ documento_fonte("nullif(trim(nr_cpf_cnpj_fornecedor), '-4')") }}
            as nr_cpf_cnpj_fornecedor,
        nm_fornecedor::varchar as nm_fornecedor,
        nm_fornecedor_rfb::varchar as nm_fornecedor_rfb,
        nullif({{ texto('cd_esfera_part_fornecedor') }}, '-4')::varchar
            as cd_esfera_part_fornecedor,
        ds_esfera_part_fornecedor::varchar as ds_esfera_part_fornecedor,
        sg_uf_fornecedor::varchar as sg_uf_fornecedor,
        nullif({{ texto('cd_municipio_fornecedor') }}, '-4')::varchar as cd_municipio_fornecedor,
        nm_municipio_fornecedor::varchar as nm_municipio_fornecedor,
        nullif({{ texto('sq_candidato_fornecedor') }}, '-4')::varchar as sq_candidato_fornecedor,
        nullif({{ texto('nr_candidato_fornecedor') }}, '-4')::varchar as nr_candidato_fornecedor,
        nullif({{ texto('cd_cargo_fornecedor') }}, '-4')::varchar as cd_cargo_fornecedor,
        ds_cargo_fornecedor::varchar as ds_cargo_fornecedor,
        nullif({{ texto('nr_partido_fornecedor') }}, '-4')::varchar as nr_partido_fornecedor,
        sg_partido_fornecedor::varchar as sg_partido_fornecedor,
        nm_partido_fornecedor::varchar as nm_partido_fornecedor,
        ds_tipo_documento::varchar as ds_tipo_documento,
        nullif({{ texto('nr_documento') }}, '-4')::varchar as nr_documento,
        nullif({{ texto('cd_origem_despesa') }}, '-4')::varchar as cd_origem_despesa,
        ds_origem_despesa::varchar as ds_origem_despesa,
        nullif({{ texto('sq_despesa') }}, '-4')::varchar as sq_despesa,
        {{ data_br('dt_despesa') }} as dt_despesa,
        ds_despesa::varchar as ds_despesa,
        {{ numero_br('vr_despesa_contratada') }} as vr_despesa_contratada,
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
            sg_ue := sg_ue,
            nm_ue := nm_ue,
            nr_cnpj_prestador_conta := nr_cnpj_prestador_conta,
            cd_cargo := cd_cargo,
            ds_cargo := ds_cargo,
            sq_candidato := sq_candidato,
            nr_candidato := nr_candidato,
            nm_candidato := nm_candidato,
            nr_cpf_candidato := nr_cpf_candidato,
            nr_cpf_vice_candidato := nr_cpf_vice_candidato,
            nr_partido := nr_partido,
            sg_partido := sg_partido,
            nm_partido := nm_partido,
            cd_tipo_fornecedor := cd_tipo_fornecedor,
            ds_tipo_fornecedor := ds_tipo_fornecedor,
            cd_cnae_fornecedor := cd_cnae_fornecedor,
            ds_cnae_fornecedor := ds_cnae_fornecedor,
            nr_cpf_cnpj_fornecedor := nr_cpf_cnpj_fornecedor,
            nm_fornecedor := nm_fornecedor,
            nm_fornecedor_rfb := nm_fornecedor_rfb,
            cd_esfera_part_fornecedor := cd_esfera_part_fornecedor,
            ds_esfera_part_fornecedor := ds_esfera_part_fornecedor,
            sg_uf_fornecedor := sg_uf_fornecedor,
            cd_municipio_fornecedor := cd_municipio_fornecedor,
            nm_municipio_fornecedor := nm_municipio_fornecedor,
            sq_candidato_fornecedor := sq_candidato_fornecedor,
            nr_candidato_fornecedor := nr_candidato_fornecedor,
            cd_cargo_fornecedor := cd_cargo_fornecedor,
            ds_cargo_fornecedor := ds_cargo_fornecedor,
            nr_partido_fornecedor := nr_partido_fornecedor,
            sg_partido_fornecedor := sg_partido_fornecedor,
            nm_partido_fornecedor := nm_partido_fornecedor,
            ds_tipo_documento := ds_tipo_documento,
            nr_documento := nr_documento,
            cd_origem_despesa := cd_origem_despesa,
            ds_origem_despesa := ds_origem_despesa,
            sq_despesa := sq_despesa,
            dt_despesa := dt_despesa,
            ds_despesa := ds_despesa,
            vr_despesa_contratada := vr_despesa_contratada
        )) as linha_original,
        case
            when trim(nr_cnpj_prestador_conta) = '-4' then 'sentinela_menos4'
            when nullif(trim(nr_cnpj_prestador_conta), '') is null then 'nao_informado'
            when regexp_matches(trim(nr_cnpj_prestador_conta), '^-[0-9]+$') then 'codigo_negativo'
        end::varchar as nr_cnpj_prestador_conta_ausencia,
        case
            when trim(nr_cpf_candidato) = '-4' then 'sentinela_menos4'
            when nullif(trim(nr_cpf_candidato), '') is null then 'nao_informado'
            when regexp_matches(trim(nr_cpf_candidato), '^-[0-9]+$') then 'codigo_negativo'
        end::varchar as nr_cpf_candidato_ausencia,
        case
            when trim(nr_cpf_vice_candidato) = '-4' then 'sentinela_menos4'
            when nullif(trim(nr_cpf_vice_candidato), '') is null then 'nao_informado'
            when regexp_matches(trim(nr_cpf_vice_candidato), '^-[0-9]+$') then 'codigo_negativo'
        end::varchar as nr_cpf_vice_candidato_ausencia,
        case
            when trim(nr_cpf_cnpj_fornecedor) = '-4' then 'sentinela_menos4'
            when nullif(trim(nr_cpf_cnpj_fornecedor), '') is null then 'nao_informado'
            when regexp_matches(trim(nr_cpf_cnpj_fornecedor), '^-[0-9]+$') then 'codigo_negativo'
        end::varchar as nr_cpf_cnpj_fornecedor_ausencia
    from {{ fonte_tse('contratadas') }}
)

select
    *,
    dt_eleicao as data_eleicao,
    'tse:' || cd_eleicao || ':' || sq_candidato as candidatura_id,
    tp_prestacao_contas as tipo_prestacao,
    dt_prestacao_contas as data_prestacao,
    {{ documento_valido('nr_cnpj_prestador_conta') }} as nr_cnpj_prestador_conta_valido,
    {{ documento_valido('nr_cpf_candidato') }} as nr_cpf_candidato_valido,
    {{ documento_valido('nr_cpf_vice_candidato') }} as nr_cpf_vice_candidato_valido,
    {{ documento_valido('nr_cpf_cnpj_fornecedor') }} as nr_cpf_cnpj_fornecedor_valido,
    nr_cpf_candidato as cpf_candidato,
    nr_cpf_candidato_ausencia as cpf_candidato_ausencia,
    {{ documento_valido('nr_cpf_candidato') }} as cpf_candidato_valido
from tipado
where year(dt_eleicao) in (2018, 2020, 2022, 2024)
