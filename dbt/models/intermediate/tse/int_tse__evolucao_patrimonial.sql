-- Todos os pares cronológicos efetivos, sem janela e sem join à ponte parlamentar.
-- Comparação descritiva: a diferença declarada não equivale a renda ou irregularidade.
with comparaveis as (
    select * from {{ ref('int_tse__patrimonio') }}
    where declaracao_efetiva and pessoa_confirmada and not empate_data_evolucao
        and patrimonio is not null and pessoa_id is not null
)
select
    a.pessoa_id,
    a.candidatura_id as candidatura_anterior_id,
    p.candidatura_id as candidatura_posterior_id,
    a.data_eleicao as data_anterior,
    p.data_eleicao as data_posterior,
    a.cobertura as cobertura_anterior,
    p.cobertura as cobertura_posterior,
    a.patrimonio as patrimonio_anterior,
    p.patrimonio as patrimonio_posterior,
    p.patrimonio - a.patrimonio as variacao_absoluta,
    case when a.patrimonio <> 0
        then (p.patrimonio - a.patrimonio) / a.patrimonio * 100 end as variacao_percentual,
    a.patrimonio = 0 as base_zero,
    'tse_evolucao_todos_pares_v1' as regra_versao
from comparaveis a
inner join comparaveis p on a.pessoa_id = p.pessoa_id and a.data_eleicao < p.data_eleicao
