-- Contratos federais na versão mais recente (o mesmo contrato reaparece em meses diferentes),
-- com o documento do fornecedor completo (para os alertas).
select
    concat('cgu:', ug_codigo, ':', contrato_numero) as contrato_id,
    *,
    case fornecedor_tipo_documento
        when 'CPF' then {{ documento_valido('fornecedor_documento') }}
        when 'CNPJ' then {{ documento_valido('fornecedor_documento') }}
        when 'INVALIDO' then false
    end as fornecedor_documento_valido,
    if(fornecedor_tipo_documento = 'CNPJ', substr(fornecedor_documento, 1, 8), null) as fornecedor_cnpj_raiz
from {{ ref('stg_cgu__contratos') }}
where ug_codigo is not null and contrato_numero is not null
qualify row_number() over (
    partition by ug_codigo, contrato_numero order by _competencia_data desc, _coleta_id desc
) = 1
