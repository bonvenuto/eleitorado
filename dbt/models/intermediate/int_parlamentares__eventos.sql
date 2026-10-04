{#- histórico permanente: --full-refresh só reconstrói a partir do replay (seção 7.4) -#}
{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='evento_id',
        full_refresh=(var('fonte_historico', 'raw') == 'replay'),
        cluster_by=['parlamentar_id'],
    )
}}

-- Eventos do cadastro de parlamentares (mudança de partido, de UF, entrada e saída).
{{ eventos_de_snapshots(
    origem=ref('int_parlamentares__snapshots'),
    chave='parlamentar_id',
    atributos=['casa', 'nome', 'uf_sigla', 'partido_sigla'],
    particao='casa',
) }}
