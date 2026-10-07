-- Privado: todas as contribuições e motivos permanecem aqui; nenhuma célula PF é liberada.
-- Pares fechados fonte/origem/esfera; em 2022 são regra explícita, não cobertura demonstrada.
with campanhas as (
    select nr_cnpj_prestador_conta as documento from {{ ref('int_tse__receitas') }}
    union
    select nr_cnpj_prestador_conta from {{ ref('int_tse__contratadas') }}
), originarios as (
    select distinct
        case when regexp_matches(coalesce(cd_eleicao, ''), '^[0-9]+$')
            and try_cast(cd_eleicao as hugeint) > 0 then cd_eleicao end as cd_eleicao,
        case when regexp_matches(coalesce(sq_prestador_contas, ''), '^[0-9]+$')
            and try_cast(sq_prestador_contas as hugeint) > 0 then sq_prestador_contas end
            as sq_prestador_contas,
        case when tipo_prestacao in (
            select distinct tipo_prestacao from {{ ref('int_tse__receitas') }}
        ) then tipo_prestacao end as tipo_prestacao,
        data_prestacao
    from {{ ref('stg_tse__doador_originario') }}
), normalizados as (
    select r.*,
        {{ nome_normalizado('ds_fonte_receita') }} as fonte_comparavel,
        {{ nome_normalizado('ds_origem_receita') }} as origem_comparavel,
        {{ nome_normalizado('ds_natureza_receita') }} as natureza_comparavel,
        {{ nome_normalizado('ds_esfera_partidaria_doador') }} as esfera_comparavel,
        {{ nome_normalizado('sg_partido_doador') }} as sigla_comparavel,
        {{ nome_normalizado('nm_partido_doador') }} as partido_comparavel,
        {% for campo in ['sq_candidato_doador', 'cd_cargo_candidato_doador',
                         'nr_candidato_doador'] %}
        case when {{ campo }} is null or trim({{ campo }}) in ('', '#NULO', '#NE', '-4', '-1')
            then 0 else try_cast({{ campo }} as bigint) end as {{ campo }}_numero,
        {% endfor %}
        exists(select 1 from campanhas c where c.documento = r.nr_cpf_cnpj_doador)
            as doador_campanha,
        exists(select 1 from originarios o
            where (o.cd_eleicao is null or o.cd_eleicao = r.cd_eleicao)
                and (o.sq_prestador_contas is null
                    or o.sq_prestador_contas = r.sq_prestador_contas)
                and (o.tipo_prestacao is null or o.data_prestacao is null
                    or (o.tipo_prestacao = r.tipo_prestacao
                        and o.data_prestacao = r.data_prestacao))) as originario_no_escopo
    from {{ ref('int_tse__receitas') }} r
), papeis as (
    select *, coalesce(
        ((upper(trim(cd_esfera_partidaria_doador)) = 'N' and esfera_comparavel = 'NACIONAL')
        or (upper(trim(cd_esfera_partidaria_doador)) = 'F'
            and esfera_comparavel = 'FEDERAL (ESTADUAL/DISTRITAL)')
        or (upper(trim(cd_esfera_partidaria_doador)) = 'M' and esfera_comparavel = 'MUNICIPAL'))
        and try_cast(nr_partido_doador as bigint) > 0
        and sigla_comparavel not in ('', '#NULO', '#NE', '-4', '-1')
        and partido_comparavel not in ('', '#NULO', '#NE', '-4', '-1')
        and sq_candidato_doador_numero = 0 and cd_cargo_candidato_doador_numero = 0
        and nr_candidato_doador_numero = 0 and not doador_campanha, false) as papel_partidario
    from normalizados
), consenso as (
    select nr_cpf_cnpj_doador,
        bool_and(papel_partidario) and count(distinct struct_pack(
            esfera := upper(trim(cd_esfera_partidaria_doador)), rotulo := esfera_comparavel,
            partido := nr_partido_doador, sigla := sigla_comparavel, nome := partido_comparavel,
            candidato := sq_candidato_doador_numero, cargo := cd_cargo_candidato_doador_numero,
            numero_candidato := nr_candidato_doador_numero)) = 1 as doador_coerente
    from papeis
    group by nr_cpf_cnpj_doador
), avaliados as (
    select p.*, coalesce(c.doador_coerente, false) as doador_coerente,
        case
            when originario_no_escopo then 'grupo_com_originarios_sem_vinculo_item_demonstrado'
            when not coalesce(fato_elegivel and candidatura_elegivel and prestacao_elegivel
                and not prestacao_ambigua and not origem_ambigua
                and not metadados_incompletos, false) then 'fato_inelegivel'
            when valor is null or valor = -4 or data is null then 'valor_ou_data_inutilizavel'
            when not coalesce((cd_fonte_receita = '0' and fonte_comparavel = 'FUNDO PARTIDARIO')
                or (cd_fonte_receita = '2' and fonte_comparavel = 'FUNDO ESPECIAL'), false)
                then 'fonte_nao_permitida'
            when not coalesce(cd_origem_receita = '10020000'
                and origem_comparavel = 'RECURSOS DE PARTIDO POLITICO', false)
                then 'origem_nao_permitida'
            when natureza_comparavel not in ('FINANCEIRO', 'ESTIMAVEL')
                then 'natureza_nao_permitida'
            when not coalesce({{ tipo_documento('p.nr_cpf_cnpj_doador') }} = 'CNPJ'
                and p.nr_cpf_cnpj_doador_valido
                and {{ documento_valido('p.nr_cpf_cnpj_doador') }}, false)
                then 'documento_nao_permitido'
            when not coalesce(c.doador_coerente, false) then 'papel_partidario_nao_demonstrado'
        end as motivo_privado
    from papeis p
    left join consenso c on p.nr_cpf_cnpj_doador = c.nr_cpf_cnpj_doador
)
select *, motivo_privado is null as publicavel,
    case natureza_comparavel when 'FINANCEIRO' then 'financeiro'
        when 'ESTIMAVEL' then 'estimavel' end::varchar as natureza_recurso,
    case when cd_fonte_receita = '0' and fonte_comparavel = 'FUNDO PARTIDARIO'
        then 'fundo_partidario' when cd_fonte_receita = '2' and fonte_comparavel = 'FUNDO ESPECIAL'
        then 'fundo_especial' end::varchar as origem_recurso,
    1::bigint as quantidade
from avaliados
