-- O fato da cota tem as mesmas linhas e o mesmo valor reembolsado que o staging, por casa e ano.
with origem as (
    select 'camara' as casa, ano, count(*) as linhas, sum(valor_reembolsado) as valor
    from {{ ref('stg_camara__ceap') }}
    group by 1, 2
    union all
    select 'senado', ano, count(*), sum(valor_reembolsado)
    from {{ ref('stg_senado__ceaps') }}
    group by 1, 2
),

fato as (
    -- o ano vem da pasta do Parquet particionado (casa=/ano=): sem arquivos, o tipo é texto
    select casa, cast(ano as bigint) as ano, count(*) as linhas, sum(valor_reembolsado) as valor
    from {{ ref('fct_despesa_cota_parlamentar') }}
    group by 1, 2
)

select *
from origem as o
full join fato as f using (casa, ano)
where o.linhas is distinct from f.linhas
    or abs(coalesce(o.valor, 0) - coalesce(f.valor, 0)) > 0.01
