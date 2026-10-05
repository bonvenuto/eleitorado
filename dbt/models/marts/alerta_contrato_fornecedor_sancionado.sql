-- Contrato federal assinado com fornecedor que tinha sanção (CEIS ou CNEP) vigente na data de
-- assinatura. É um indício para investigar: a abrangência da sanção varia e só aparecem as
-- sanções vistas desde a primeira coleta.
with contratos as (
    select
        *,
        {{ chave_correspondencia('fornecedor_tipo_documento', 'fornecedor_documento') }} as chave
    from {{ ref('int_contratos_federais') }}
    where fornecedor_documento_valido and data_assinatura is not null

),

sancoes as (
    {{ sancoes_para_alerta() }}
),

cruzadas as (
    select
        c.contrato_id,
        s.sancao_id,
        {{ tipo_correspondencia('c.fornecedor_tipo_documento', 'c.fornecedor_documento', 's.documento') }}
            as tipo_correspondencia,
        c.contrato_numero,
        c.orgao_nome,
        {{ mascarar_cpfs_em_texto('c.ug_nome') }} as ug_nome,
        {{ mascarar_cpfs_em_texto('c.objeto') }} as objeto,
        c.data_assinatura,

        c.valor_final,
        {{ mascarar_cpfs_em_texto('c.fornecedor_nome') }} as fornecedor_nome,
        {{ documento_publico('c.fornecedor_documento') }} as fornecedor_documento,
        s.cadastro,
        s.categoria as categoria_sancao,
        s.abrangencia,
        s.orgao_sancionador,
        s.data_inicio as sancao_data_inicio,
        s.data_fim as sancao_data_fim,
        c._coleta_id as contrato_coleta_id,
        s._coleta_id as sancao_coleta_id,
        s.data_evento as sancao_data_evento
    from contratos as c
    join sancoes as s
        on s.chave = c.chave
        and c.data_assinatura between s.data_inicio and coalesce(s.data_fim, date '9999-12-31')
)

select
    md5(concat('contrato_fornecedor_sancionado|', contrato_id, '|', sancao_id)) as alerta_id,
    * exclude (sancao_data_evento),
    'Contrato federal assinado com fornecedor que tinha sanção vigente no CEIS/CNEP '
    || '(correspondência por CPF, CNPJ ou raiz do CNPJ)' as regra
from cruzadas
qualify row_number() over (
    partition by contrato_id, sancao_id
    order by if(tipo_correspondencia = 'cnpj_raiz', 1, 0), sancao_data_evento desc
) = 1
