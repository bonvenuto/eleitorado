-- Declarações privadas: ausência não é zero e origens concorrentes nunca são somadas.
with candidaturas as (
    select *, {{ nome_normalizado('nm_candidato') }} as nome_comparavel
    from {{ ref('int_tse__candidaturas') }}
), pessoas as (
    select cpf_candidato,
        count(distinct nome_comparavel) = 1 and bool_and(nome_comparavel != '')
            and bool_and(candidatura_elegivel) as pessoa_coerente
    from candidaturas
    where cpf_candidato_valido and cpf_candidato_ausencia is null
        and {{ tipo_documento('cpf_candidato') }} = 'CPF'
        and {{ documento_valido('cpf_candidato') }}
    group by cpf_candidato
), bens as (
    select candidatura_id,
        count(*) as quantidade_itens,
        count(distinct struct_pack(ano := ano_arquivo, versao := versao_id,
            layout := layout_id)) as quantidade_origens,
        bool_or(ano_arquivo is null or versao_id is null or layout_id is null
            or cd_eleicao is null or sq_candidato is null) as metadados_incompletos,
        bool_or(vr_bem_candidato is null or nr_ordem_bem_candidato is null
            or vr_bem_candidato = -4) as itens_invalidos,
        bool_or(data_eleicao is null) as data_ausente,
        min(data_eleicao) as primeira_data,
        max(data_eleicao) as ultima_data,
        case when count(distinct struct_pack(ano := ano_arquivo, versao := versao_id,
            layout := layout_id)) = 1 then sum(vr_bem_candidato) end as patrimonio_observado,
        list(b) as itens_privados,
        list(distinct struct_pack(ano_arquivo := ano_arquivo, versao_id := versao_id,
            layout_id := layout_id)) as origens_privadas
    from {{ ref('stg_tse__bens') }} b
    group by candidatura_id
), cobertura as (
    select c.candidatura_id, c.cd_eleicao, c.sq_candidato, c.data_eleicao,
        c.cpf_candidato, c.nome_comparavel,
        coalesce(b.quantidade_itens, 0) as quantidade_itens,
        coalesce(b.quantidade_origens, 0) as quantidade_origens,
        b.patrimonio_observado, b.itens_privados, b.origens_privadas,
        coalesce(p.pessoa_coerente and c.cpf_candidato_valido
            and c.cpf_candidato_ausencia is null and c.candidatura_elegivel, false)
            as pessoa_confirmada,
        case
            when b.quantidade_itens is null then 'sem_declaracao'
            when not c.candidatura_elegivel or c.cd_eleicao is null
                or c.sq_candidato is null then 'candidatura_pendente'
            when b.quantidade_origens <> 1 then 'origem_ambigua'
            when b.metadados_incompletos then 'metadados_incompletos'
            when b.itens_invalidos then 'itens_invalidos'
            when b.data_ausente or c.data_eleicao is null
                or b.primeira_data <> c.data_eleicao or b.ultima_data <> c.data_eleicao
                then 'data_incompativel'
            else 'declaracao_efetiva'
        end as cobertura
    from candidaturas c
    left join bens b using (candidatura_id)
    left join pessoas p using (cpf_candidato)
), efetivas as (
    select *, cobertura = 'declaracao_efetiva' as declaracao_efetiva,
        case when cobertura = 'declaracao_efetiva' then patrimonio_observado end as patrimonio,
        case when pessoa_confirmada then 'pessoa:' || cpf_candidato end as pessoa_id
    from cobertura
), datas as (
    select pessoa_id, data_eleicao, count(*) as quantidade_declaracoes_data
    from efetivas
    where declaracao_efetiva and pessoa_confirmada
    group by pessoa_id, data_eleicao
)
select e.*,
    coalesce(d.quantidade_declaracoes_data > 1, false) as empate_data_evolucao,
    case
        when not e.pessoa_confirmada then 'pessoa_pendente'
        when not e.declaracao_efetiva then e.cobertura
        when d.quantidade_declaracoes_data > 1 then 'empate_data'
        else 'comparavel'
    end as cobertura_evolucao,
    'tse_patrimonio_v1' as regra_versao
from efetivas e
left join datas d using (pessoa_id, data_eleicao)
