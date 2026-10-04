{#- Snapshot de onde partem os históricos: o raw (padrão) ou, numa reconstrução completa
    (`--full-refresh --vars '{fonte_historico: replay}'`), o dataset `replay`, carregado antes
    com `coletor recarregar --destino replay` a partir dos originais (seção 7.4 da spec). -#}
{% macro fonte_snapshot(orgao, recurso) -%}
{%- set fonte = var('fonte_historico', 'raw') -%}
{%- if fonte == 'replay' -%}
{{ source('replay', orgao ~ '__' ~ recurso) }}
{%- elif fonte == 'raw' -%}
{{ source('raw_' ~ orgao, recurso) }}
{%- else -%}
{{ exceptions.raise_compiler_error("fonte_historico deve ser raw ou replay, não " ~ fonte) }}
{%- endif -%}
{%- endmacro %}
