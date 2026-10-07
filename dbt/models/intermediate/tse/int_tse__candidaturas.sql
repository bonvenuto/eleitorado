-- Chave oficial por eleição; nenhuma variante conflitante é escolhida como confirmada.
with consolidado as (
    select
        cd_eleicao,
        sq_candidato,
        'tse:' || cd_eleicao || ':' || sq_candidato as candidatura_id,
        case
            when min(cd_tipo_eleicao) is not distinct from max(cd_tipo_eleicao)
                and count(cd_tipo_eleicao) in (0, count(*))
                then min(cd_tipo_eleicao)
        end as cd_tipo_eleicao,
        case
            when min(nm_tipo_eleicao) is not distinct from max(nm_tipo_eleicao)
                and count(nm_tipo_eleicao) in (0, count(*))
                then min(nm_tipo_eleicao)
        end as nm_tipo_eleicao,
        case
            when min(nr_turno) is not distinct from max(nr_turno)
                and count(nr_turno) in (0, count(*))
                then min(nr_turno)
        end as nr_turno,
        case
            when min(ds_eleicao) is not distinct from max(ds_eleicao)
                and count(ds_eleicao) in (0, count(*))
                then min(ds_eleicao)
        end as ds_eleicao,
        case
            when min(dt_eleicao) is not distinct from max(dt_eleicao)
                and count(dt_eleicao) in (0, count(*))
                then min(dt_eleicao)
        end as dt_eleicao,
        case
            when min(tp_abrangencia) is not distinct from max(tp_abrangencia)
                and count(tp_abrangencia) in (0, count(*))
                then min(tp_abrangencia)
        end as tp_abrangencia,
        case
            when min(sg_uf) is not distinct from max(sg_uf)
                and count(sg_uf) in (0, count(*))
                then min(sg_uf)
        end as sg_uf,
        case
            when min(sg_ue) is not distinct from max(sg_ue)
                and count(sg_ue) in (0, count(*))
                then min(sg_ue)
        end as sg_ue,
        case
            when min(nm_ue) is not distinct from max(nm_ue)
                and count(nm_ue) in (0, count(*))
                then min(nm_ue)
        end as nm_ue,
        case
            when min(cd_cargo) is not distinct from max(cd_cargo)
                and count(cd_cargo) in (0, count(*))
                then min(cd_cargo)
        end as cd_cargo,
        case
            when min(ds_cargo) is not distinct from max(ds_cargo)
                and count(ds_cargo) in (0, count(*))
                then min(ds_cargo)
        end as ds_cargo,
        case
            when min(nr_candidato) is not distinct from max(nr_candidato)
                and count(nr_candidato) in (0, count(*))
                then min(nr_candidato)
        end as nr_candidato,
        case
            when min(nm_candidato) is not distinct from max(nm_candidato)
                and count(nm_candidato) in (0, count(*))
                then min(nm_candidato)
        end as nm_candidato,
        case
            when min(nm_urna_candidato) is not distinct from max(nm_urna_candidato)
                and count(nm_urna_candidato) in (0, count(*))
                then min(nm_urna_candidato)
        end as nm_urna_candidato,
        case
            when min(nm_social_candidato) is not distinct from max(nm_social_candidato)
                and count(nm_social_candidato) in (0, count(*))
                then min(nm_social_candidato)
        end as nm_social_candidato,
        case
            when min(nr_cpf_candidato) is not distinct from max(nr_cpf_candidato)
                and count(nr_cpf_candidato) in (0, count(*))
                then min(nr_cpf_candidato)
        end as nr_cpf_candidato,
        case
            when min(ds_email) is not distinct from max(ds_email)
                and count(ds_email) in (0, count(*))
                then min(ds_email)
        end as ds_email,
        case
            when min(cd_situacao_candidatura) is not distinct from max(cd_situacao_candidatura)
                and count(cd_situacao_candidatura) in (0, count(*))
                then min(cd_situacao_candidatura)
        end as cd_situacao_candidatura,
        case
            when min(ds_situacao_candidatura) is not distinct from max(ds_situacao_candidatura)
                and count(ds_situacao_candidatura) in (0, count(*))
                then min(ds_situacao_candidatura)
        end as ds_situacao_candidatura,
        case
            when min(tp_agremiacao) is not distinct from max(tp_agremiacao)
                and count(tp_agremiacao) in (0, count(*))
                then min(tp_agremiacao)
        end as tp_agremiacao,
        case
            when min(nr_partido) is not distinct from max(nr_partido)
                and count(nr_partido) in (0, count(*))
                then min(nr_partido)
        end as nr_partido,
        case
            when min(sg_partido) is not distinct from max(sg_partido)
                and count(sg_partido) in (0, count(*))
                then min(sg_partido)
        end as sg_partido,
        case
            when min(nm_partido) is not distinct from max(nm_partido)
                and count(nm_partido) in (0, count(*))
                then min(nm_partido)
        end as nm_partido,
        case
            when min(nr_federacao) is not distinct from max(nr_federacao)
                and count(nr_federacao) in (0, count(*))
                then min(nr_federacao)
        end as nr_federacao,
        case
            when min(nm_federacao) is not distinct from max(nm_federacao)
                and count(nm_federacao) in (0, count(*))
                then min(nm_federacao)
        end as nm_federacao,
        case
            when min(sg_federacao) is not distinct from max(sg_federacao)
                and count(sg_federacao) in (0, count(*))
                then min(sg_federacao)
        end as sg_federacao,
        case
            when min(ds_composicao_federacao) is not distinct from max(ds_composicao_federacao)
                and count(ds_composicao_federacao) in (0, count(*))
                then min(ds_composicao_federacao)
        end as ds_composicao_federacao,
        case
            when min(sq_coligacao) is not distinct from max(sq_coligacao)
                and count(sq_coligacao) in (0, count(*))
                then min(sq_coligacao)
        end as sq_coligacao,
        case
            when min(nm_coligacao) is not distinct from max(nm_coligacao)
                and count(nm_coligacao) in (0, count(*))
                then min(nm_coligacao)
        end as nm_coligacao,
        case
            when min(ds_composicao_coligacao) is not distinct from max(ds_composicao_coligacao)
                and count(ds_composicao_coligacao) in (0, count(*))
                then min(ds_composicao_coligacao)
        end as ds_composicao_coligacao,
        case
            when min(sg_uf_nascimento) is not distinct from max(sg_uf_nascimento)
                and count(sg_uf_nascimento) in (0, count(*))
                then min(sg_uf_nascimento)
        end as sg_uf_nascimento,
        case
            when min(dt_nascimento) is not distinct from max(dt_nascimento)
                and count(dt_nascimento) in (0, count(*))
                then min(dt_nascimento)
        end as dt_nascimento,
        case
            when min(nr_titulo_eleitoral_candidato) is not distinct from max(nr_titulo_eleitoral_candidato)
                and count(nr_titulo_eleitoral_candidato) in (0, count(*))
                then min(nr_titulo_eleitoral_candidato)
        end as nr_titulo_eleitoral_candidato,
        case
            when min(cd_genero) is not distinct from max(cd_genero)
                and count(cd_genero) in (0, count(*))
                then min(cd_genero)
        end as cd_genero,
        case
            when min(ds_genero) is not distinct from max(ds_genero)
                and count(ds_genero) in (0, count(*))
                then min(ds_genero)
        end as ds_genero,
        case
            when min(cd_grau_instrucao) is not distinct from max(cd_grau_instrucao)
                and count(cd_grau_instrucao) in (0, count(*))
                then min(cd_grau_instrucao)
        end as cd_grau_instrucao,
        case
            when min(ds_grau_instrucao) is not distinct from max(ds_grau_instrucao)
                and count(ds_grau_instrucao) in (0, count(*))
                then min(ds_grau_instrucao)
        end as ds_grau_instrucao,
        case
            when min(cd_estado_civil) is not distinct from max(cd_estado_civil)
                and count(cd_estado_civil) in (0, count(*))
                then min(cd_estado_civil)
        end as cd_estado_civil,
        case
            when min(ds_estado_civil) is not distinct from max(ds_estado_civil)
                and count(ds_estado_civil) in (0, count(*))
                then min(ds_estado_civil)
        end as ds_estado_civil,
        case
            when min(cd_cor_raca) is not distinct from max(cd_cor_raca)
                and count(cd_cor_raca) in (0, count(*))
                then min(cd_cor_raca)
        end as cd_cor_raca,
        case
            when min(ds_cor_raca) is not distinct from max(ds_cor_raca)
                and count(ds_cor_raca) in (0, count(*))
                then min(ds_cor_raca)
        end as ds_cor_raca,
        case
            when min(cd_ocupacao) is not distinct from max(cd_ocupacao)
                and count(cd_ocupacao) in (0, count(*))
                then min(cd_ocupacao)
        end as cd_ocupacao,
        case
            when min(ds_ocupacao) is not distinct from max(ds_ocupacao)
                and count(ds_ocupacao) in (0, count(*))
                then min(ds_ocupacao)
        end as ds_ocupacao,
        case
            when min(cd_sit_tot_turno) is not distinct from max(cd_sit_tot_turno)
                and count(cd_sit_tot_turno) in (0, count(*))
                then min(cd_sit_tot_turno)
        end as cd_sit_tot_turno,
        case
            when min(ds_sit_tot_turno) is not distinct from max(ds_sit_tot_turno)
                and count(ds_sit_tot_turno) in (0, count(*))
                then min(ds_sit_tot_turno)
        end as ds_sit_tot_turno,
        case
            when min(data_eleicao) is not distinct from max(data_eleicao)
                and count(data_eleicao) in (0, count(*))
                then min(data_eleicao)
        end as data_eleicao,
        case
            when min(cpf_candidato) is not distinct from max(cpf_candidato)
                and count(cpf_candidato) in (0, count(*))
                then min(cpf_candidato)
        end as cpf_candidato,
        case
            when min(cpf_candidato_ausencia) is not distinct from max(cpf_candidato_ausencia)
                and count(cpf_candidato_ausencia) in (0, count(*))
                then min(cpf_candidato_ausencia)
        end as cpf_candidato_ausencia,
        case
            when min(cpf_candidato_valido) is not distinct from max(cpf_candidato_valido)
                and count(cpf_candidato_valido) in (0, count(*))
                then min(cpf_candidato_valido)
        end as cpf_candidato_valido,
        count(*) as quantidade_registros,
        list(s) as variantes_privadas,
        list(distinct struct_pack(ano_arquivo := ano_arquivo,
            versao_id := versao_id, layout_id := layout_id)) as proveniencias_privadas,
        ((min(cd_tipo_eleicao) is distinct from max(cd_tipo_eleicao)
                or count(cd_tipo_eleicao) not in (0, count(*)))
            or (min(nm_tipo_eleicao) is distinct from max(nm_tipo_eleicao)
                or count(nm_tipo_eleicao) not in (0, count(*)))
            or (min(nr_turno) is distinct from max(nr_turno)
                or count(nr_turno) not in (0, count(*)))
            or (min(ds_eleicao) is distinct from max(ds_eleicao)
                or count(ds_eleicao) not in (0, count(*)))
            or (min(dt_eleicao) is distinct from max(dt_eleicao)
                or count(dt_eleicao) not in (0, count(*)))
            or (min(tp_abrangencia) is distinct from max(tp_abrangencia)
                or count(tp_abrangencia) not in (0, count(*)))
            or (min(sg_uf) is distinct from max(sg_uf)
                or count(sg_uf) not in (0, count(*)))
            or (min(sg_ue) is distinct from max(sg_ue)
                or count(sg_ue) not in (0, count(*)))
            or (min(nm_ue) is distinct from max(nm_ue)
                or count(nm_ue) not in (0, count(*)))
            or (min(cd_cargo) is distinct from max(cd_cargo)
                or count(cd_cargo) not in (0, count(*)))
            or (min(ds_cargo) is distinct from max(ds_cargo)
                or count(ds_cargo) not in (0, count(*)))
            or (min(nr_candidato) is distinct from max(nr_candidato)
                or count(nr_candidato) not in (0, count(*)))
            or (min(nm_candidato) is distinct from max(nm_candidato)
                or count(nm_candidato) not in (0, count(*)))
            or (min(nm_urna_candidato) is distinct from max(nm_urna_candidato)
                or count(nm_urna_candidato) not in (0, count(*)))
            or (min(nm_social_candidato) is distinct from max(nm_social_candidato)
                or count(nm_social_candidato) not in (0, count(*)))
            or (min(nr_cpf_candidato) is distinct from max(nr_cpf_candidato)
                or count(nr_cpf_candidato) not in (0, count(*)))
            or (min(ds_email) is distinct from max(ds_email)
                or count(ds_email) not in (0, count(*)))
            or (min(cd_situacao_candidatura) is distinct from max(cd_situacao_candidatura)
                or count(cd_situacao_candidatura) not in (0, count(*)))
            or (min(ds_situacao_candidatura) is distinct from max(ds_situacao_candidatura)
                or count(ds_situacao_candidatura) not in (0, count(*)))
            or (min(tp_agremiacao) is distinct from max(tp_agremiacao)
                or count(tp_agremiacao) not in (0, count(*)))
            or (min(nr_partido) is distinct from max(nr_partido)
                or count(nr_partido) not in (0, count(*)))
            or (min(sg_partido) is distinct from max(sg_partido)
                or count(sg_partido) not in (0, count(*)))
            or (min(nm_partido) is distinct from max(nm_partido)
                or count(nm_partido) not in (0, count(*)))
            or (min(nr_federacao) is distinct from max(nr_federacao)
                or count(nr_federacao) not in (0, count(*)))
            or (min(nm_federacao) is distinct from max(nm_federacao)
                or count(nm_federacao) not in (0, count(*)))
            or (min(sg_federacao) is distinct from max(sg_federacao)
                or count(sg_federacao) not in (0, count(*)))
            or (min(ds_composicao_federacao) is distinct from max(ds_composicao_federacao)
                or count(ds_composicao_federacao) not in (0, count(*)))
            or (min(sq_coligacao) is distinct from max(sq_coligacao)
                or count(sq_coligacao) not in (0, count(*)))
            or (min(nm_coligacao) is distinct from max(nm_coligacao)
                or count(nm_coligacao) not in (0, count(*)))
            or (min(ds_composicao_coligacao) is distinct from max(ds_composicao_coligacao)
                or count(ds_composicao_coligacao) not in (0, count(*)))
            or (min(sg_uf_nascimento) is distinct from max(sg_uf_nascimento)
                or count(sg_uf_nascimento) not in (0, count(*)))
            or (min(dt_nascimento) is distinct from max(dt_nascimento)
                or count(dt_nascimento) not in (0, count(*)))
            or (min(nr_titulo_eleitoral_candidato) is distinct from max(nr_titulo_eleitoral_candidato)
                or count(nr_titulo_eleitoral_candidato) not in (0, count(*)))
            or (min(cd_genero) is distinct from max(cd_genero)
                or count(cd_genero) not in (0, count(*)))
            or (min(ds_genero) is distinct from max(ds_genero)
                or count(ds_genero) not in (0, count(*)))
            or (min(cd_grau_instrucao) is distinct from max(cd_grau_instrucao)
                or count(cd_grau_instrucao) not in (0, count(*)))
            or (min(ds_grau_instrucao) is distinct from max(ds_grau_instrucao)
                or count(ds_grau_instrucao) not in (0, count(*)))
            or (min(cd_estado_civil) is distinct from max(cd_estado_civil)
                or count(cd_estado_civil) not in (0, count(*)))
            or (min(ds_estado_civil) is distinct from max(ds_estado_civil)
                or count(ds_estado_civil) not in (0, count(*)))
            or (min(cd_cor_raca) is distinct from max(cd_cor_raca)
                or count(cd_cor_raca) not in (0, count(*)))
            or (min(ds_cor_raca) is distinct from max(ds_cor_raca)
                or count(ds_cor_raca) not in (0, count(*)))
            or (min(cd_ocupacao) is distinct from max(cd_ocupacao)
                or count(cd_ocupacao) not in (0, count(*)))
            or (min(ds_ocupacao) is distinct from max(ds_ocupacao)
                or count(ds_ocupacao) not in (0, count(*)))
            or (min(cd_sit_tot_turno) is distinct from max(cd_sit_tot_turno)
                or count(cd_sit_tot_turno) not in (0, count(*)))
            or (min(ds_sit_tot_turno) is distinct from max(ds_sit_tot_turno)
                or count(ds_sit_tot_turno) not in (0, count(*)))
            or (min(data_eleicao) is distinct from max(data_eleicao)
                or count(data_eleicao) not in (0, count(*)))
            or (min(cpf_candidato) is distinct from max(cpf_candidato)
                or count(cpf_candidato) not in (0, count(*)))
            or (min(cpf_candidato_ausencia) is distinct from max(cpf_candidato_ausencia)
                or count(cpf_candidato_ausencia) not in (0, count(*)))
            or (min(cpf_candidato_valido) is distinct from max(cpf_candidato_valido)
                or count(cpf_candidato_valido) not in (0, count(*)))) as conflito_cadastral
    from {{ ref('stg_tse__candidaturas') }} as s
    where year(data_eleicao) in (2018, 2020, 2022, 2024)
    group by cd_eleicao, sq_candidato
)

select
    *,
    not conflito_cadastral and cd_eleicao is not null and sq_candidato is not null
        as candidatura_elegivel
from consolidado
