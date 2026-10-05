-- Versão vigente de cada contrato do PNCP (a de atualização mais recente), com o documento
-- completo do fornecedor.
select
    *,
    case fornecedor_tipo_documento
        when 'CPF' then {{ documento_valido('fornecedor_documento') }}
        when 'CNPJ' then {{ documento_valido('fornecedor_documento') }}
        when 'INVALIDO' then false
    end as fornecedor_documento_valido,
    if(fornecedor_tipo_documento = 'CNPJ', substr(fornecedor_documento, 1, 8), null) as fornecedor_cnpj_raiz
from {{ ref('stg_pncp__contratos') }}
where contrato_pncp_id is not null
qualify row_number() over (
    partition by contrato_pncp_id
    order by data_atualizacao desc nulls last, numero_retificacao desc nulls last, origem
) = 1
