{{ config(location=tse_saida_mart('fct_patrimonio_declarado')) }}
-- Agrega tipos somente após gate da declaração completa/única. Sem descrição ou pessoa.
select b.candidatura_id,
    {{ mascarar_cpfs_em_texto('b.cd_tipo_bem_candidato') }} as tipo_bem_codigo,
    count(*)::bigint as quantidade, sum(b.vr_bem_candidato)::decimal(38,2) as valor
from {{ ref('stg_tse__bens') }} b
inner join {{ ref('int_tse__patrimonio') }} p on b.candidatura_id = p.candidatura_id
where p.declaracao_efetiva
group by b.candidatura_id, {{ mascarar_cpfs_em_texto('b.cd_tipo_bem_candidato') }}
