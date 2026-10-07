{{ config(location=tse_saida_mart('fct_despesa_campanha_pj')) }}
-- Dois tipos de fato separados. A soma dos tipos não representa gasto único.
with publicos as (
    {% for modelo, tipo in [('contratadas', 'contratacao'), ('pagamentos', 'pagamento')] %}
    select f.candidatura_id, '{{ tipo }}'::varchar as tipo_fato,
        p.fornecedor_documento as fornecedor_cnpj, f.data::date as data,
        f.valor::decimal(38,2) as valor
    from {{ ref('int_tse__' ~ modelo) }} f
    inner join {{ ref('int_tse__fornecedores_elegiveis') }} p
        on f.cd_eleicao = p.cd_eleicao and f.sq_prestador_contas = p.sq_prestador_contas
        and f.sq_despesa = p.sq_despesa and f.tipo_prestacao = p.tipo_prestacao
        and f.data_prestacao = p.data_prestacao and f.candidatura_id = p.candidatura_id
        and f.fornecedor_documento = p.fornecedor_documento
    where f.fato_elegivel and p.publicavel and f.valor is not null
        and f.valor <> -4 and f.data is not null
    {% if not loop.last %} union all {% endif %}
    {% endfor %}
)
select
    md5(to_json(struct_pack(candidatura := candidatura_id, tipo := tipo_fato,
        fornecedor := fornecedor_cnpj, data := data, valor := valor))) || '-' || cast(
        row_number() over (partition by candidatura_id, tipo_fato, fornecedor_cnpj, data, valor)
        as varchar) as despesa_id,
    candidatura_id, tipo_fato, fornecedor_cnpj, data, valor
from publicos
