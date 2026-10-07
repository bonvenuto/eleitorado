{{ config(location=tse_saida_mart('dim_candidatura')) }}
-- Allowlist pública: nome de urna consensual; situação é o resultado eleitoral.
select
    candidatura_id, cd_eleicao, sq_candidato, data_eleicao,
    {{ mascarar_cpfs_em_texto('cd_cargo') }} as cargo_codigo,
    {{ mascarar_cpfs_em_texto('ds_cargo') }} as cargo,
    {{ mascarar_cpfs_em_texto('sg_uf') }} as uf_sigla,
    {{ mascarar_cpfs_em_texto('sg_ue') }} as localidade_codigo,
    {{ mascarar_cpfs_em_texto('nm_ue') }} as localidade,
    {{ mascarar_cpfs_em_texto('nm_urna_candidato') }} as nome_publico,
    {{ mascarar_cpfs_em_texto('nr_partido') }} as partido_numero,
    {{ mascarar_cpfs_em_texto('sg_partido') }} as partido_sigla,
    {{ mascarar_cpfs_em_texto('ds_sit_tot_turno') }} as situacao_eleitoral
from {{ ref('int_tse__candidaturas') }}
where candidatura_elegivel
