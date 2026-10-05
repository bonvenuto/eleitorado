-- Despesa de cota com CPF ou CNPJ de fornecedor preenchido e inválido.
-- Ficam de fora documentos vazios, CPFs que o Senado já publica mascarados e os códigos
-- internos da Câmara (`000000000000NN`).
select
    md5(concat('cota_documento_invalido|', despesa_id)) as alerta_id,
    despesa_id,
    casa,
    parlamentar_id,
    nome_beneficiario,
    data_emissao,
    categoria,
    valor_reembolsado,
    {{ mascarar_cpfs_em_texto('fornecedor_nome') }} as fornecedor_nome,
    {{ documento_publico('fornecedor_documento') }} as documento_publicado,
    if(fornecedor_tipo_documento = 'INVALIDO', 'tamanho', 'digito_verificador') as motivo,
    'Documento de fornecedor com tamanho ou dígito verificador inválido' as regra,
    _coleta_id
from {{ ref('int_cota__despesas') }}
where fornecedor_tipo_documento in ('CPF', 'CNPJ', 'INVALIDO')
    and not fornecedor_documento_valido
