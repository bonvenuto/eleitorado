-- Exploratório privado: fato TSE x fato C1 x relação, sem agregação financeira entre fontes.
-- _coleta_id não é hash físico. C1 legado mutável não pertence à edição atômica C2.
with fatos_tse as (
    {% for modelo, tipo in [('contratadas', 'contratacao'), ('pagamentos', 'pagamento')] %}
    select f.candidatura_id, '{{ tipo }}'::varchar as tipo_fato_tse,
        f.item_id, f.ano_arquivo, f.versao_id, f.layout_id,
        f.data::date as data_tse, f.valor::decimal(38,2) as valor_tse,
        {{ cnpj_raiz('p.fornecedor_documento') }} as raiz,
        to_json(f) as evidencia_tse_privada
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
), ponte as (
    select distinct candidatura_id, parlamentar_id
    from {{ ref('int_tse__vinculos_parlamentares') }}
    where estado = 'confirmado' and parlamentar_id is not null
), cota as (
    select t.*, 'cota'::varchar as origem_c1, c.despesa_id as fato_c1_id,
        c.parlamentar_id, 'identidade_confirmada'::varchar as estado_autoria,
        c.data_emissao::date as data_c1, c.valor_reembolsado::decimal(38,2) as valor_c1,
        'valor_reembolsado'::varchar as semantica_valor_c1, c._coleta_id as coleta_c1_id
    from fatos_tse t
    inner join ponte p using (candidatura_id)
    inner join {{ ref('fct_despesa_cota_parlamentar') }} c
        on c.parlamentar_id = p.parlamentar_id and c.fornecedor_cnpj_raiz = t.raiz
    where c.fornecedor_tipo_documento = 'CNPJ' and c.fornecedor_documento_valido
        and c.data_emissao_valida and c.data_emissao is not null
        and c.valor_reembolsado is not null and c.data_emissao > t.data_tse
), autores_contextuais as (
    select distinct autor_codigo, parlamentar_id
    from {{ ref('dim_autor_emenda') }} where parlamentar_id is not null
), emenda as (
    select t.*, 'emenda_pagamento'::varchar as origem_c1, c.pagamento_linha_id as fato_c1_id,
        p.parlamentar_id, 'autoria_contextual_nome'::varchar as estado_autoria,
        c.data_documento::date as data_c1, c.valor_pago::decimal(38,2) as valor_c1,
        'valor_pago'::varchar as semantica_valor_c1, c._coleta_id as coleta_c1_id
    from fatos_tse t
    inner join ponte p using (candidatura_id)
    inner join autores_contextuais a on a.parlamentar_id = p.parlamentar_id
    inner join {{ ref('int_cgu__emendas_pagamentos') }} c
        on c.autor_codigo = a.autor_codigo and c.favorecido_cnpj_raiz = t.raiz
    where c.fase_despesa = 'Pagamento' and c.favorecido_tipo_documento = 'CNPJ'
        and c.favorecido_documento_valido and c.data_documento is not null
        and c.valor_pago is not null and c.data_documento > t.data_tse
), contrato as (
    select t.*, 'contrato'::varchar as origem_c1, c.contrato_id as fato_c1_id,
        null::varchar as parlamentar_id, 'sem_autoria_demonstrada'::varchar as estado_autoria,
        c.data_assinatura::date as data_c1, c.valor_final::decimal(38,2) as valor_c1,
        'valor_final'::varchar as semantica_valor_c1, c._coleta_id as coleta_c1_id
    from fatos_tse t
    inner join {{ ref('fct_contrato_federal') }} c on c.fornecedor_cnpj_raiz = t.raiz
    where c.fornecedor_tipo_documento = 'CNPJ' and c.fornecedor_documento_valido
        and not c.valor_suspeito and c.data_assinatura is not null
        and c.valor_final is not null and c.data_assinatura > t.data_tse
), contextos as (
    select * from cota union all select * from emenda union all select * from contrato
), receita as (
    select cnpj_raiz,
        list_sort(list(distinct competencia_receita)) as competencias_receita,
        count(distinct competencia_receita) = 1 and bool_and(competencia_receita is not null)
            as competencia_inequivoca,
        min(competencia_receita) as competencia_receita
    from {{ ref('int_rfb__empresas') }} group by cnpj_raiz
)
select
    md5(to_json(struct_pack(tipo := c.tipo_fato_tse, item := c.item_id,
        ano := c.ano_arquivo, versao := c.versao_id, origem := c.origem_c1,
        fato := c.fato_c1_id, parlamentar := c.parlamentar_id))) as cruzamento_id,
    c.*,
    list_value(c.coleta_c1_id) as versoes_entradas_c1,
    'gates_documentais_temporais_aplicados'::varchar as estado_qualidade,
    r.competencias_receita,
    case when r.competencia_inequivoca then r.competencia_receita end as competencia_receita,
    case when r.competencia_inequivoca then 'cadastro_observado'
        else 'cobertura_pendente' end::varchar as cobertura_receita,
    true as snapshot_legado_nao_atomico,
    'tse_cruzamentos_v1'::varchar as regra_versao
from contextos c
left join receita r on c.raiz = r.cnpj_raiz
