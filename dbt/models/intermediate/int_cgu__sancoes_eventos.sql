{#- histórico permanente: --full-refresh só reconstrói a partir do replay (seção 7.4) -#}
{{
    config(
        materialized='incremental',
        incremental_strategy='delete+insert',
        unique_key='evento_id',
        full_refresh=(var('fonte_historico', 'raw') == 'replay'),
    )
}}

-- Eventos de inclusão, alteração e exclusão das sanções do CEIS e do CNEP.
-- Permanente: o raw guarda só 60 dias de snapshots (seção 6.3 da spec).
{{ eventos_de_snapshots(
    origem=ref('stg_cgu__sancoes'),
    chave='sancao_id',
    atributos=[
        'cadastro', 'tipo_pessoa', 'documento', 'nome_sancionado', 'razao_social_receita',
        'categoria', 'valor_multa', 'data_inicio', 'data_fim', 'data_publicacao',
        'data_transito_julgado', 'abrangencia', 'orgao_sancionador', 'uf_orgao_sancionador',
        'esfera_orgao_sancionador', 'fundamentacao_legal', 'numero_processo',
    ],
    particao='cadastro',
) }}
