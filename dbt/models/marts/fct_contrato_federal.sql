-- Contratos do Poder Executivo federal (Portal da Transparência, 2013 em diante). CPF mascarado.
select
    contrato_id,
    contrato_numero,
    {{ mascarar_cpfs_em_texto('objeto') }} as objeto,
    fundamento_legal, modalidade, situacao,
    orgao_superior_codigo, orgao_superior_nome, orgao_codigo, orgao_nome,
    ug_codigo,
    {{ mascarar_cpfs_em_texto('ug_nome') }} as ug_nome,
    data_assinatura, data_publicacao, data_inicio_vigencia, data_fim_vigencia,
    {{ documento_publico('fornecedor_documento') }} as fornecedor_documento,
    fornecedor_tipo_documento,
    fornecedor_documento_valido,
    fornecedor_cnpj_raiz,
    {{ mascarar_cpfs_em_texto('fornecedor_nome') }} as fornecedor_nome,
    valor_inicial,
    valor_final,
    licitacao_numero,
    licitacao_ug_codigo,
    licitacao_modalidade_codigo,
    _competencia as competencia_publicacao,
    _coleta_id
from {{ ref('int_cgu__contratos') }}
