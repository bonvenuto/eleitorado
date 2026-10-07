-- Privado. Projetar metadados distintos ANTES de relacionar parcelas; nunca juntar itens.
-- NULL participa do consenso. Os metadados conflitantes permanecem nas listas privadas.
with metadados as (
    select distinct
        cd_eleicao, sq_prestador_contas, sq_despesa, tipo_prestacao, data_prestacao,
        candidatura_id, sq_candidato, fornecedor_documento, fornecedor_documento_valido
    from {{ ref('int_tse__contratadas') }}
), consenso as (
    select
        cd_eleicao, sq_prestador_contas, sq_despesa, tipo_prestacao, data_prestacao,
        count(*) as quantidade_metadados,
        list(struct_pack(candidatura_id := candidatura_id, sq_candidato := sq_candidato,
            fornecedor_documento := fornecedor_documento,
            fornecedor_documento_valido := fornecedor_documento_valido)) as metadados_privados
    from metadados
    group by cd_eleicao, sq_prestador_contas, sq_despesa, tipo_prestacao, data_prestacao
), elegibilidade as (
    select cd_eleicao, sq_prestador_contas, sq_despesa, tipo_prestacao, data_prestacao,
        bool_and(coalesce(mapa_contratada_elegivel, false)) as itens_elegiveis,
        bool_and(coalesce(candidatura_elegivel, false))
            and count(distinct struct_pack(candidatura := candidatura_id,
                candidato := sq_candidato)) = 1 as candidatura_elegivel
    from {{ ref('int_tse__contratadas') }}
    group by cd_eleicao, sq_prestador_contas, sq_despesa, tipo_prestacao, data_prestacao
)
select
    c.*,
    coalesce(e.candidatura_elegivel, false) as candidatura_elegivel,
    case when quantidade_metadados = 1 then metadados_privados[1].candidatura_id end
        as candidatura_id,
    case when quantidade_metadados = 1 then metadados_privados[1].sq_candidato end
        as sq_candidato,
    case when quantidade_metadados = 1 then metadados_privados[1].fornecedor_documento end
        as fornecedor_documento,
    case when quantidade_metadados = 1 then metadados_privados[1].fornecedor_documento_valido end
        as fornecedor_documento_valido,
    quantidade_metadados <> 1 as conflito_mapa,
    quantidade_metadados = 1 and coalesce(e.itens_elegiveis, false)
        and c.cd_eleicao is not null and c.sq_prestador_contas is not null
        and c.sq_despesa is not null and c.tipo_prestacao is not null
        and c.data_prestacao is not null as mapa_elegivel
from consenso c
left join elegibilidade e
    on c.cd_eleicao is not distinct from e.cd_eleicao
    and c.sq_prestador_contas is not distinct from e.sq_prestador_contas
    and c.sq_despesa is not distinct from e.sq_despesa
    and c.tipo_prestacao is not distinct from e.tipo_prestacao
    and c.data_prestacao is not distinct from e.data_prestacao
