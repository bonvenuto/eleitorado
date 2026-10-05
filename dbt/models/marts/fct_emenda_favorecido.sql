-- Favorecidos de emendas por mês (snapshot mais recente). CPF sempre mascarado.
select
    md5(concat(hash_linha, '-', cast(row_number() over (partition by hash_linha order by emenda_codigo) as varchar)))
        as favorecido_linha_id,
    emenda_codigo,
    autor_codigo,
    numero_emenda,
    tipo_emenda,
    mes_referencia,
    {{ documento_publico('favorecido_documento') }} as favorecido_documento,
    favorecido_tipo_documento,
    if(favorecido_tipo_documento = 'CNPJ', substr(favorecido_documento, 1, 8), null) as favorecido_cnpj_raiz,
    {{ mascarar_cpfs_em_texto('favorecido_nome') }} as favorecido_nome,
    natureza_juridica,
    tipo_favorecido,
    favorecido_uf,
    favorecido_municipio,
    valor_recebido,
    _coleta_id
from {{ ref('stg_cgu__emendas_favorecidos') }}
