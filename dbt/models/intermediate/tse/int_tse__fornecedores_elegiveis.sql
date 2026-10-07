-- Privado: consenso de classificação por contratação, sem expandir as parcelas.
-- PJ declarada não comprova natureza cadastral na Receita; cobertura institucional observada.
with institucionais as (
    select nr_cnpj_prestador_conta as documento
    from {{ ref('int_tse__contratadas') }}
    union
    select nr_cnpj_prestador_conta from {{ ref('int_tse__receitas') }}
    union
    select nr_cpf_cnpj_doador from {{ ref('int_tse__receitas') }}
    where {{ nome_normalizado('ds_origem_receita') }} = 'RECURSOS DE PARTIDO POLITICO'
), normalizados as (
    select c.*,
        {{ nome_normalizado('ds_tipo_fornecedor') }} as tipo_declarado,
        {% for campo in ['sq_candidato_fornecedor', 'cd_cargo_fornecedor',
                         'nr_partido_fornecedor'] %}
        case when {{ campo }} is null or trim({{ campo }}) in ('', '#NULO', '#NE', '-4')
            then 0 else try_cast({{ campo }} as bigint) end as {{ campo }}_numero,
        {% endfor %}
        exists(select 1 from institucionais i where i.documento = c.fornecedor_documento)
            as documento_institucional
    from {{ ref('int_tse__contratadas') }} c
), classificados as (
    select *, case
        when {{ tipo_documento('fornecedor_documento') }} <> 'CNPJ'
            or not coalesce(fornecedor_documento_valido, false)
            or not coalesce({{ documento_valido('fornecedor_documento') }}, false)
            then 'documento_invalido'
        when documento_institucional or sq_candidato_fornecedor_numero > 0
            or cd_cargo_fornecedor_numero > 0 then 'campanha_ou_institucional'
        when nr_partido_fornecedor_numero > 0
            then 'partido'
        when tipo_declarado = 'PESSOA FISICA' then 'pf'
        when tipo_declarado <> 'PESSOA JURIDICA'
            or sq_candidato_fornecedor_numero is null or cd_cargo_fornecedor_numero is null
            or nr_partido_fornecedor_numero is null
            or sq_candidato_fornecedor_numero < 0 or cd_cargo_fornecedor_numero < 0
            or nr_partido_fornecedor_numero < 0
            or coalesce(trim(cd_esfera_part_fornecedor), '')
                not in ('', '#NULO', '#NE', '-4', '-1')
            or coalesce(trim(ds_esfera_part_fornecedor), '')
                not in ('', '#NULO', '#NE', '-4', '-1')
            or coalesce(trim(sg_partido_fornecedor), '') not in ('', '#NULO', '#NE', '-4')
            or coalesce(trim(nm_partido_fornecedor), '') not in ('', '#NULO', '#NE', '-4')
            then 'incerto'
        else 'pj_declarada'
    end as classificacao
    from normalizados
), consenso as (
    select cd_eleicao, sq_prestador_contas, sq_despesa, tipo_prestacao, data_prestacao,
        count(distinct struct_pack(candidatura := candidatura_id,
            documento := fornecedor_documento, categoria := classificacao)) as alternativas,
        min(candidatura_id) as candidatura_id,
        min(fornecedor_documento) as fornecedor_documento,
        bool_and(coalesce(fato_elegivel, false) and classificacao = 'pj_declarada')
            as itens_publicaveis,
        list(distinct classificacao) as classificacoes_privadas
    from classificados
    group by cd_eleicao, sq_prestador_contas, sq_despesa, tipo_prestacao, data_prestacao
)
select cd_eleicao, sq_prestador_contas, sq_despesa, tipo_prestacao, data_prestacao,
    case when alternativas = 1 then candidatura_id end as candidatura_id,
    case when alternativas = 1 then fornecedor_documento end as fornecedor_documento,
    classificacoes_privadas,
    alternativas = 1 and itens_publicaveis
        and cd_eleicao is not null and sq_prestador_contas is not null
        and sq_despesa is not null and tipo_prestacao is not null and data_prestacao is not null
        as publicavel
from consenso
