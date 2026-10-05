-- Participantes de licitações do Poder Executivo federal (2013 a 2024-04), por item.
select
    _coleta_id,
    _competencia,
    _competencia_data,
    {{ texto('numero_licitacao') }} as licitacao_numero,
    {{ texto('codigo_ug') }} as ug_codigo,
    {{ texto('codigo_modalidade_compra') }} as modalidade_codigo,
    {{ texto('codigo_orgao') }} as orgao_codigo,
    {{ texto('nome_orgao') }} as orgao_nome,
    {{ texto('codigo_item_compra') }} as item_codigo,
    {{ texto('descricao_item_compra') }} as item_descricao,
    {{ documento_fonte('codigo_participante') }} as participante_documento,
    {{ tipo_documento_fonte('codigo_participante') }} as participante_tipo_documento,
    {{ texto('nome_participante') }} as participante_nome,
    {{ texto('flag_vencedor') }} = 'SIM' as vencedor,
    md5(to_json(struct_pack(*columns(* exclude (
        _coleta_id, _competencia, _competencia_data, _linha, _arquivo_original, _carregado_em
    ))))) as hash_linha
from {{ source('raw_cgu', 'licitacoes_participantes') }}
