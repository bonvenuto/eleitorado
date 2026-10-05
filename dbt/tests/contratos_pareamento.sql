{{ config(severity='warn') }}

-- Aviso quando, nos anos em que as duas fontes se sobrepõem, menos da metade dos contratos
-- federais do PNCP (sem contar empenhos) encontra par no Portal: a regra de pareamento pode ter
-- enfraquecido.
with pncp as (
    select fonte
    from {{ ref('int_contratos_federais') }}
    where id_pncp is not null
        and tipo_contrato ilike 'contrato%'
        and year(data_assinatura) between 2022 and year(current_date) - 1
)

select count(*) as contratos, count_if(fonte = 'ambas') as pareados
from pncp
having count(*) > 0 and count_if(fonte = 'ambas') < 0.5 * count(*)
