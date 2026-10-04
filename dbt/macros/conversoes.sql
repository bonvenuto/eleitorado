{#- Texto do raw para tipos. Cada fonte tem seu formato (seção 7.3 da spec). -#}

{% macro texto(coluna) -%}
nullif(trim({{ coluna }}), '')
{%- endmacro %}

{#- CGU: vírgula decimal e ponto de milhar ("1.234,56") -#}
{% macro numero_br(coluna) -%}
safe_cast(replace(replace({{ texto(coluna) }}, '.', ''), ',', '.') as numeric)
{%- endmacro %}

{#- CGU: "dd/mm/aaaa" -#}
{% macro data_br(coluna) -%}
safe.parse_date('%d/%m/%Y', {{ texto(coluna) }})
{%- endmacro %}
