{#- Cada target tem o próprio arquivo .duckdb: o schema é sempre o configurado (staging,
    intermediate, marts) ou, sem configuração, o do target (main). -#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
