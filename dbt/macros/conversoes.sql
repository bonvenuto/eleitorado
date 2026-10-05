{#- Texto do raw para tipos. Cada fonte tem seu formato (seção 7.3 da spec). -#}

{% macro texto(coluna) -%}
nullif(trim({{ coluna }}), '')
{%- endmacro %}

{#- valores monetários: até 38 dígitos, 2 casas -#}
{% macro numero(expressao) -%}
try_cast({{ expressao }} as decimal(38, 2))
{%- endmacro %}

{#- CGU: vírgula decimal e ponto de milhar ("1.234,56") -#}
{% macro numero_br(coluna) -%}
{{ numero("replace(replace(" ~ texto(coluna) ~ ", '.', ''), ',', '.')") }}
{%- endmacro %}

{#- CGU: "dd/mm/aaaa" -#}
{% macro data_br(coluna) -%}
try_strptime({{ texto(coluna) }}, '%d/%m/%Y')::date
{%- endmacro %}
