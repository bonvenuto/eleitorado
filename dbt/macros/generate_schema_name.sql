{#- prod: o schema configurado (staging, intermediate, marts);
    dev: <dataset do target>_<schema>;
    ci: tudo no dataset do target, porque a conta do CI só grava no dataset ci -#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none or target.name == 'ci' -%}
        {{ target.schema }}
    {%- elif target.name == 'prod' -%}
        {{ custom_schema_name | trim }}
    {%- else -%}
        {{ target.schema }}_{{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
