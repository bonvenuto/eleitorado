{{ config(location=tse_saida_mart('fct_receita_campanha_resumo')) }}
-- Somente subtotais aprovados; nunca soma contribuições PF suprimidas.
select candidatura_id, natureza_recurso, origem_recurso,
    sum(valor)::decimal(38,2) as valor, sum(quantidade)::bigint as quantidade
from {{ ref('int_tse__receitas_publicaveis') }}
where publicavel
group by candidatura_id, natureza_recurso, origem_recurso
