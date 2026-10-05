-- Despesa de cota cujo fornecedor tinha sanção (CEIS ou CNEP) na data da despesa.
-- É um indício para investigar, não a constatação de irregularidade: a cota reembolsa gastos
-- do parlamentar (não é contratação pública) e a abrangência da sanção varia.
-- Cobertura: só sanções vistas desde a primeira coleta (a CGU publica apenas o arquivo do dia).
-- chave de correspondência: CPF completo para pessoa física, raiz do CNPJ para pessoa jurídica
-- (matriz e filiais são a mesma pessoa jurídica); um join por igualdade, sem OR
with despesas as (
    select
        *,
        {{ chave_correspondencia('fornecedor_tipo_documento', 'fornecedor_documento') }} as chave
    from {{ ref('int_cota__despesas') }}
    where fornecedor_documento_valido and data_emissao is not null
),

-- qualquer versão já vista de cada sanção (exclusões não são versões)
sancoes as (
    {{ sancoes_para_alerta() }}
),

cruzadas as (
    select
        d.despesa_id,
        s.sancao_id,
        {{ tipo_correspondencia('d.fornecedor_tipo_documento', 'd.fornecedor_documento', 's.documento') }}
            as tipo_correspondencia,
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
        s._coleta_id as sancao_coleta_id,
        s.data_evento as sancao_data_evento
    from despesas as d
    join sancoes as s
        on s.chave = d.chave
        and d.data_emissao between s.data_inicio and coalesce(s.data_fim, date '9999-12-31')
)

select
    md5(concat('cota_fornecedor_sancionado|', despesa_id, '|', sancao_id)) as alerta_id,
    * exclude (sancao_data_evento),
    'Despesa de cota com fornecedor que tinha sanção vigente no CEIS/CNEP na data de emissão '
    || '(correspondência por CPF, CNPJ ou raiz do CNPJ)' as regra
from cruzadas
-- uma linha por (despesa, sanção): CNPJ completo antes da raiz, versão mais recente da sanção
qualify row_number() over (
    partition by despesa_id, sancao_id
    order by if(tipo_correspondencia = 'cnpj_raiz', 1, 0), sancao_data_evento desc
) = 1
