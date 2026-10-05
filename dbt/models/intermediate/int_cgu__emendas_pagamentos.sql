-- Documentos de despesa de emendas, com o documento do favorecido completo (para os alertas).
select
    md5(concat(hash_linha, '-', cast(row_number() over (partition by hash_linha order by _competencia) as varchar)))
        as pagamento_linha_id,
    *,
    case favorecido_tipo_documento
        when 'CPF' then {{ documento_valido('favorecido_documento') }}
        when 'CNPJ' then {{ documento_valido('favorecido_documento') }}
        when 'INVALIDO' then false
    end as favorecido_documento_valido,
    if(favorecido_tipo_documento = 'CNPJ', substr(favorecido_documento, 1, 8), null) as favorecido_cnpj_raiz
from {{ ref('stg_cgu__emendas_documentos') }}
