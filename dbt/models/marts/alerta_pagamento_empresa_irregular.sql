-- Despesa de cota, pagamento de emenda ou contrato com empresa que já estava baixada, inapta,
-- suspensa ou nula na Receita na data do fato. Vale a situação do estabelecimento exato (CNPJ de
-- 14 posições) ou, sem ele, a da matriz. Sucessão (incorporação, fusão, cisão total) não conta: a
-- empresa sucessora existe. Indício para investigar.
with fatos as (
    {{ rfb_fatos() }}
),

estabelecimentos as (
    select * from {{ ref('int_rfb__estabelecimentos') }}
),

matrizes as (
    select * from estabelecimentos
    where matriz
    qualify row_number() over (partition by cnpj_raiz order by cnpj) = 1
),

alvos as (
    select
        f.*,
        coalesce(e.cnpj, m.cnpj) as estabelecimento_cnpj,
        e.cnpj is not null as estabelecimento_exato
    from fatos as f
    left join estabelecimentos as e on e.cnpj = f.cnpj
    left join matrizes as m on m.cnpj_raiz = f.cnpj_raiz
)

select
    md5(concat('pagamento_empresa_irregular|', a.origem, '|', a.fato_id)) as alerta_id,
    a.origem,
    a.fato_id,
    a.data_fato,
    a.valor,
    a.cnpj,
    {{ mascarar_cpfs_em_texto('emp.razao_social') }} as razao_social,
    a.estabelecimento_cnpj,
    a.estabelecimento_exato,
    s.situacao,
    s.data_situacao,
    s.motivo as motivo_situacao,
    a.data_fato - s.data_situacao as dias_desde_a_situacao,
    a.parlamentar_id,
    'Fato com empresa baixada, inapta, suspensa ou nula na Receita desde antes da data do fato '
    || '(situação do estabelecimento exato ou da matriz; sucessões excluídas)' as regra
from alvos as a
join estabelecimentos as s on s.cnpj = a.estabelecimento_cnpj
left join {{ ref('int_rfb__empresas') }} as emp on emp.cnpj_raiz = a.cnpj_raiz
where s.situacao_codigo in ('01', '03', '04', '08')
    and s.data_situacao <= a.data_fato
    and coalesce(s.motivo_codigo, '') not in ('02', '03', '04')
