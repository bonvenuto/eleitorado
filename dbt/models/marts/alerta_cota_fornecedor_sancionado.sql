-- Despesa de cota cujo fornecedor tinha sanção (CEIS ou CNEP) na data da despesa.
-- É um indício para investigar, não a constatação de irregularidade: a cota reembolsa gastos
-- do parlamentar (não é contratação pública) e a abrangência da sanção varia.
-- Cobertura: só sanções vistas desde a primeira coleta (a CGU publica apenas o arquivo do dia).
with despesas as (
    select *
    from {{ ref('int_cota__despesas') }}
    where fornecedor_documento_valido and data_emissao is not null
),

-- qualquer versão já vista de cada sanção (exclusões não são versões)
sancoes as (
    select distinct
        sancao_id, cadastro, tipo_pessoa, documento,
        {{ tipo_documento('documento') }} as tipo_documento,
        {{ cnpj_raiz('documento') }} as cnpj_raiz,
        nome_sancionado, categoria, abrangencia, orgao_sancionador, data_inicio, data_fim, _coleta_id
    from {{ ref('int_cgu__sancoes_eventos') }}
    where evento != 'exclusao' and data_inicio is not null
),

cruzadas as (
    select
        d.despesa_id,
        s.sancao_id,
        case
            when d.fornecedor_tipo_documento = 'CPF' then 'cpf'
            when d.fornecedor_documento = s.documento then 'cnpj'
            else 'cnpj_raiz'
        end as tipo_correspondencia,
        d.casa,
        d.parlamentar_id,
        d.nome_beneficiario,
        d.data_emissao,
        d.categoria as categoria_despesa,
        d.valor_reembolsado,
        {{ mascarar_cpfs_em_texto('d.fornecedor_nome') }} as fornecedor_nome,
        {{ documento_publico('d.fornecedor_documento') }} as fornecedor_documento,
        s.cadastro,
        s.categoria as categoria_sancao,
        s.abrangencia,
        s.orgao_sancionador,
        s.data_inicio as sancao_data_inicio,
        s.data_fim as sancao_data_fim,
        d._coleta_id as despesa_coleta_id,
        s._coleta_id as sancao_coleta_id
    from despesas as d
    join sancoes as s
        on (
            (d.fornecedor_tipo_documento = 'CPF' and s.tipo_documento = 'CPF'
                and d.fornecedor_documento = s.documento)
            or (d.fornecedor_tipo_documento = 'CNPJ' and s.tipo_documento = 'CNPJ'
                and d.fornecedor_cnpj_raiz = s.cnpj_raiz)
        )
        and d.data_emissao between s.data_inicio and coalesce(s.data_fim, date '9999-12-31')
)

select
    to_hex(md5(concat('cota_fornecedor_sancionado|', despesa_id, '|', sancao_id))) as alerta_id,
    *,
    'Despesa de cota com fornecedor que tinha sanção vigente no CEIS/CNEP na data de emissão '
    || '(correspondência por CPF, CNPJ ou raiz do CNPJ)' as regra
from cruzadas
-- uma linha por (despesa, sanção), preferindo o CNPJ completo à raiz
qualify row_number() over (
    partition by despesa_id, sancao_id
    order by if(tipo_correspondencia = 'cnpj_raiz', 1, 0), sancao_coleta_id
) = 1
