-- Ponte privada: fatos financeiros nunca recebem join expansivo desta relação.
with candidaturas as (
    select *, {{ nome_normalizado('nm_candidato') }} as nome_comparavel
    from {{ ref('int_tse__candidaturas') }}
), nomes_cpf as (
    select cpf_candidato,
        count(distinct nome_comparavel) = 1 and bool_and(nome_comparavel != '')
            and bool_and(candidatura_elegivel) as cadastro_coerente
    from candidaturas
    where cpf_candidato_valido and cpf_candidato_ausencia is null
    group by cpf_candidato
), evidencias as (
    select 'camara:' || id_deputado as parlamentar_id,
        {{ documento_fonte('cpf') }} as cpf,
        {{ nome_normalizado('nome_civil') }} as nome_comparavel,
        'camara_detalhe' as origem,
        to_json(struct_pack(coleta := _coleta_id, data := data_referencia,
            nome := nome_civil, documento := cpf)) as evidencia_privada
    from {{ ref('stg_camara__deputados_detalhe') }}
    where id_deputado is not null
    union all
    select 'camara:' || id_deputado, {{ documento_fonte('cpf_parlamentar') }},
        {{ nome_normalizado('nome_beneficiario') }}, 'camara_ceap',
        to_json(struct_pack(coleta := _coleta_id, competencia := _competencia,
            linha := _linha, nome := nome_beneficiario, documento := cpf_parlamentar))
    from {{ ref('stg_camara__ceap') }}
    where id_deputado is not null
    union all
    select 'senado:' || id_senador, null::varchar,
        {{ nome_normalizado('nome_completo') }}, 'senado_cadastro_sem_cpf',
        to_json(struct_pack(coleta := _coleta_id, data := data_referencia,
            nome := nome_completo))
    from {{ ref('stg_senado__senadores') }}
    where id_senador is not null
), validas as (
    select *, coalesce({{ tipo_documento('cpf') }} = 'CPF'
        and {{ documento_valido('cpf') }}, false) as cpf_valido
    from evidencias
), oficial_cpf as (
    select cpf, count(distinct nome_comparavel) = 1
        and bool_and(nome_comparavel != '') as oficial_coerente
    from validas where cpf_valido group by cpf
), oficial_parlamentar as (
    select parlamentar_id, count(distinct cpf) = 1 as documento_inequivoco
    from validas where cpf_valido group by parlamentar_id
), agrupadas as (
    select parlamentar_id, cpf, cpf_valido, nome_comparavel, origem,
        list_sort(list(distinct evidencia_privada)) as evidencias_privadas
    from validas
    group by parlamentar_id, cpf, cpf_valido, nome_comparavel, origem
), ligacoes as (
    select c.candidatura_id, e.parlamentar_id, e.origem,
        case when c.candidatura_elegivel and c.cpf_candidato_valido
            and c.cpf_candidato_ausencia is null and e.cpf_valido
            and c.cpf_candidato = e.cpf and c.nome_comparavel = e.nome_comparavel
            and c.nome_comparavel != '' and n.cadastro_coerente
            and o.oficial_coerente and p.documento_inequivoco
            then 'confirmado'
            when e.parlamentar_id is not null then 'ambiguo'
            else 'ausente' end as estado,
        e.evidencias_privadas
    from candidaturas c
    left join agrupadas e on (c.cpf_candidato_valido and c.cpf_candidato_ausencia is null
            and e.cpf_valido and c.cpf_candidato = e.cpf)
        or (c.nome_comparavel != '' and c.nome_comparavel = e.nome_comparavel)
    left join nomes_cpf n on c.cpf_candidato = n.cpf_candidato
    left join oficial_cpf o on e.cpf = o.cpf
    left join oficial_parlamentar p on e.parlamentar_id = p.parlamentar_id
)
select *,
    case estado when 'confirmado' then 'cpf_nome_coerente'
        when 'ambiguo' then 'revisao_pendente' else 'sem_evidencia' end as metodo,
    case when parlamentar_id is not null then md5(to_json(evidencias_privadas)) end as evidencia_id,
    'tse_identidade_v1' as regra_versao
from ligacoes
