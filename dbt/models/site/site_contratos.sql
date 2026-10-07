-- Contratos federais por empresa (raiz do CNPJ) e órgão, para o site. Valores implausíveis
-- (`valor_suspeito`) ficam de fora.
select
    fornecedor_cnpj_raiz as cnpj_raiz,
    orgao_nome,
    sum(valor_final) as valor,
    count(*) as contratos
from {{ ref('fct_contrato_federal') }}
where fornecedor_tipo_documento = 'CNPJ' and not valor_suspeito
group by fornecedor_cnpj_raiz, orgao_nome
