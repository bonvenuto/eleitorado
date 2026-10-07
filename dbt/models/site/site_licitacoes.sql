-- Licitações federais vencidas por empresa (raiz do CNPJ), para o site.
select
    participante_cnpj_raiz as cnpj_raiz,
    count(distinct licitacao_id) as vencidas
from {{ ref('fct_licitacao_vencedor') }}
where participante_tipo_documento = 'CNPJ'
group by participante_cnpj_raiz
