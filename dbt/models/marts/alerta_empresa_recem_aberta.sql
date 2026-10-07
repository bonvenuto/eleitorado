-- Contrato ou pagamento de emenda de pelo menos R$ 50 mil, ou despesa de cota de pelo menos
-- R$ 10 mil, com empresa aberta até 180 dias antes. A abertura é o início de atividade mais antigo
-- entre os estabelecimentos. Fato anterior à abertura sai como tipo próprio (em geral, contrato
-- transferido para uma sucessora). Consórcio de Sociedades (natureza 2151) fica de fora: é criado
-- para o contrato. Indício para investigar.
with fatos as (
    {{ rfb_fatos() }}
),

empresas as (
    select * from {{ ref('int_rfb__empresas') }}
    where data_abertura is not null and natureza_juridica_codigo != '2151'
)

select
    md5(concat('empresa_recem_aberta|', f.origem, '|', f.fato_id)) as alerta_id,
    f.origem,
    f.fato_id,
    f.data_fato,
    f.valor,
    f.cnpj,
    {{ mascarar_cpfs_em_texto('e.razao_social') }} as razao_social,
    e.natureza_juridica,
    e.capital_social,
    e.data_abertura,
    f.data_fato - e.data_abertura as dias_desde_a_abertura,
    if(f.data_fato < e.data_abertura, 'fato_antes_da_abertura', 'recem_aberta') as tipo,
    f.parlamentar_id,
    'Fato até 180 dias depois da abertura da empresa (ou antes dela), de pelo menos R$ 50 mil em '
    || 'contrato ou emenda ou R$ 10 mil na cota; consórcios excluídos' as regra
from fatos as f
join empresas as e on e.cnpj_raiz = f.cnpj_raiz
where f.data_fato - e.data_abertura <= 180
    and f.valor >= if(f.origem = 'cota', 10000, 50000)
