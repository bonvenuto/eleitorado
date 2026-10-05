-- Contratos do Poder Executivo federal das duas fontes, com o documento completo (para os alertas).
-- Par Portal x PNCP: UG/unidade + número do contrato sem zeros à esquerda + ano. Havendo par, vale
-- o PNCP (chave nacional e retificações). Empenhos do PNCP não existem no Portal e ficam só no PNCP.
with cgu as (
    select
        *,
        -- NNNNNAAAA: número + ano; fora desse formato não há par (concat ignoraria nulos)
        case when regexp_matches(contrato_numero, '^[0-9]{5,}$') then concat(
            ug_codigo, '|',
            ltrim(left(contrato_numero, length(contrato_numero) - 4), '0'), '|',
            right(contrato_numero, 4)
        ) end as par
    from {{ ref('int_cgu__contratos') }}
),

pncp as (
    select
        *,
        -- só números puramente numéricos têm par (empenhos como 2026NE000397 ficam sem)
        case when regexp_matches(numero_contrato, '^[0-9]+$') and ano_contrato is not null then concat(
            unidade_codigo, '|', ltrim(numero_contrato, '0'), '|', cast(ano_contrato as varchar)
        ) end as par


    from {{ ref('int_pncp__contratos') }}
    where esfera = 'F' and poder = 'E'
),

unidas as (
    select
        coalesce('pncp:' || p.contrato_pncp_id, c.contrato_id) as contrato_id,
        c.contrato_id as id_cgu,
        p.contrato_pncp_id as id_pncp,
        case
            when p.contrato_pncp_id is not null and c.contrato_id is not null then 'ambas'
            when p.contrato_pncp_id is not null then 'pncp'
            else 'cgu'
        end as fonte,
        coalesce(p.numero_contrato, c.contrato_numero) as contrato_numero,
        coalesce(p.unidade_codigo, c.ug_codigo) as ug_codigo,
        coalesce(p.unidade_nome, c.ug_nome) as ug_nome,
        coalesce(p.orgao_nome, c.orgao_nome) as orgao_nome,
        c.orgao_superior_nome,
        coalesce(p.objeto, c.objeto) as objeto,
        p.tipo_contrato,
        c.modalidade,
        coalesce(p.data_assinatura, c.data_assinatura) as data_assinatura,
        coalesce(p.data_inicio_vigencia, c.data_inicio_vigencia) as data_inicio_vigencia,
        coalesce(p.data_fim_vigencia, c.data_fim_vigencia) as data_fim_vigencia,
        coalesce(p.fornecedor_documento, c.fornecedor_documento) as fornecedor_documento,
        coalesce(p.fornecedor_tipo_documento, c.fornecedor_tipo_documento) as fornecedor_tipo_documento,
        coalesce(p.fornecedor_documento_valido, c.fornecedor_documento_valido) as fornecedor_documento_valido,
        coalesce(p.fornecedor_cnpj_raiz, c.fornecedor_cnpj_raiz) as fornecedor_cnpj_raiz,
        coalesce(p.fornecedor_nome, c.fornecedor_nome) as fornecedor_nome,
        coalesce(p.valor_inicial, c.valor_inicial) as valor_inicial,
        coalesce(p.valor_global, c.valor_final) as valor_final,
        p.compra_pncp_id,
        c.licitacao_numero,
        p.emenda_parlamentar,
        coalesce(p._coleta_id, c._coleta_id) as _coleta_id
    from pncp as p
    full join cgu as c
        on c.par = p.par
)

select *
from unidas
qualify row_number() over (partition by contrato_id order by id_cgu nulls last) = 1
