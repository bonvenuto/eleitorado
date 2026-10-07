{{ config(location=tse_saida_mart('monitor_tse')) }}
-- Allowlist técnica. Sem auditoria financeira PF, relógio de build ou identidade circular.
-- entradas_id é alias do digest privado validado; nunca hash de CPF ou de nome.
with contexto as ({{ tse_contexto_sql() }}), selecionadas as (
    {% set ns = namespace(linhas=[]) %}
    {% set fontes = var('tse_fontes', {}) %}
    {% set proveniencia = var('tse_proveniencia', {}) %}
    {% for familia, arquivos in fontes.items() %}
      {% for arquivo in arquivos %}
        {% set meta = proveniencia[arquivo] %}
        {% if meta.versao_id is not none %}
          {% do ns.linhas.append("select '" ~ familia ~ "'::varchar as familia, "
              ~ meta.ano_arquivo ~ "::integer as ano_arquivo, '" ~ meta.versao_id
              ~ "'::varchar as versao_id, '" ~ meta.layout_id ~ "'::varchar as layout_id") %}
        {% endif %}
      {% endfor %}
    {% endfor %}
    {% if ns.linhas %} {{ ns.linhas | join(' union all ') }}
    {% else %}
      select null::varchar as familia, null::integer as ano_arquivo,
          null::varchar as versao_id, null::varchar as layout_id where false
    {% endif %}
), coletas_selecionadas as (
    {% for familia in ['candidaturas', 'bens', 'receitas', 'contratadas', 'pagamentos', 'doador_originario'] %}
    select distinct '{{ familia }}'::varchar as familia, ano_arquivo, versao_id, layout_id,
        _coleta_id as coleta_id
    from {{ ref('stg_tse__' ~ familia) }}
    {% if not loop.last %} union all {% endif %}
    {% endfor %}
), vinculos as (
    select s.familia, s.ano_arquivo, s.versao_id, s.layout_id,
        case s.familia when 'candidaturas' then 'candidaturas'
            when 'bens' then 'bens' else 'contas' end as recurso,
        bool_and(m.coleta_id is not null and m.status in ('carregada', 'sem_alteracao')
            and regexp_full_match(m.sha256_arquivo, '[0-9a-f]{64}')
            and try_cast(m.finalizada_em as timestamp) is not null
            and m.orgao = 'tse'
            and m.recurso = case s.familia when 'candidaturas' then 'candidaturas'
                when 'bens' then 'bens' else 'contas' end
            and m.competencia = s.ano_arquivo::varchar) as vinculo_completo,
        count(distinct m.sha256_arquivo) = 1 as hash_inequivoco,
        min(m.sha256_arquivo) as sha256_arquivo,
        max(m.finalizada_em) as coletado_em
    from coletas_selecionadas s
    left join {{ ref('stg_meta__coletas') }} m using (coleta_id)
    group by s.familia, s.ano_arquivo, s.versao_id, s.layout_id
), eventos as (
    select s.familia, s.ano_arquivo, s.versao_id, s.layout_id,
        max(try_cast(m.finalizada_em as timestamp)) as rechecado_em
    from vinculos s
    inner join {{ ref('stg_meta__coletas') }} m
        on m.orgao = 'tse' and m.recurso = s.recurso
        and m.competencia = s.ano_arquivo::varchar and m.sha256_arquivo = s.sha256_arquivo
    where s.vinculo_completo and s.hash_inequivoco
        and m.status in ('carregada', 'sem_alteracao')
        and m.finalizada_em >= s.coletado_em
    group by s.familia, s.ano_arquivo, s.versao_id, s.layout_id
)
select distinct c.selecao_id, c.entradas_id, s.familia, s.ano_arquivo, s.versao_id, s.layout_id,
    e.rechecado_em, 30::integer as prazo_dias,
    case when e.rechecado_em is null then 'pendente' else 'vinculada' end::varchar as cobertura,
    'financeira_privada'::varchar as auditoria
from selecionadas s
cross join contexto c
left join eventos e using (familia, ano_arquivo, versao_id, layout_id)
order by s.familia, s.ano_arquivo, s.versao_id, s.layout_id
