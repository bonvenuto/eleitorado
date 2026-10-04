{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='evento_id',
        cluster_by=['parlamentar_id'],
    )
}}

-- Eventos do cadastro de parlamentares (mudança de partido, de UF, entrada e saída).
{{ eventos_de_snapshots(
    origem=ref('int_parlamentares__snapshots'),
    chave='parlamentar_id',
    atributos=['casa', 'nome', 'uf_sigla', 'partido_sigla'],
) }}
