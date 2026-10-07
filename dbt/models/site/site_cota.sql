-- Cota parlamentar agregada para o site (parlamentar, ano, categoria e fornecedor). Só despesas do
-- próprio parlamentar (sem a cota de liderança) e sem data de emissão impossível.
select
    parlamentar_id,
    ano,
    categoria,
    fornecedor_documento,
    max(fornecedor_nome) as fornecedor_nome,
    max(fornecedor_cnpj_raiz) as fornecedor_cnpj_raiz,
    sum(valor_reembolsado) as valor,
    count(*) as despesas
from {{ ref('fct_despesa_cota_parlamentar') }}
where tipo_beneficiario = 'parlamentar' and parlamentar_id is not null and data_emissao_valida
group by parlamentar_id, ano, categoria, fornecedor_documento
