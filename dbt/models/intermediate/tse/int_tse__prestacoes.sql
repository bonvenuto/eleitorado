-- Gate conservador privado; não resolve vigência nem escolhe exportação concorrente.
-- A ausência de uma família não comprova cobertura; apenas linhas observadas participam.
with entradas as (
{% for familia in ['receitas', 'contratadas', 'pagamentos'] %}
    select cd_eleicao, sq_prestador_contas, tipo_prestacao, data_prestacao,
        ano_arquivo, versao_id
    from {{ ref('stg_tse__' ~ familia) }}
    {% if not loop.last %} union all {% endif %}
{% endfor %}
), grupos as (
    select
        cd_eleicao,
        sq_prestador_contas,
        count(*) as quantidade_registros,
        count(distinct struct_pack(tipo := tipo_prestacao, data := data_prestacao))
            as quantidade_prestacoes,
        count(distinct struct_pack(ano := ano_arquivo, versao := versao_id))
            as quantidade_origens,
        bool_or(tipo_prestacao is null or data_prestacao is null
            or ano_arquivo is null or versao_id is null) as metadados_incompletos,
        list(distinct struct_pack(tipo := tipo_prestacao, data := data_prestacao))
            as prestacoes_privadas,
        list(distinct struct_pack(ano_arquivo := ano_arquivo, versao_id := versao_id))
            as origens_privadas
    from entradas
    group by cd_eleicao, sq_prestador_contas
)
select
    *,
    quantidade_prestacoes <> 1 as prestacao_ambigua,
    quantidade_origens <> 1 as origem_ambigua,
    quantidade_prestacoes = 1 and quantidade_origens = 1 and not metadados_incompletos
        and cd_eleicao is not null and sq_prestador_contas is not null as prestacao_elegivel
from grupos
