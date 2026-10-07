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

{#- Receita (CNPJ): "aaaammdd"; "00000000" e vazio são "sem data" -#}
{% macro data_rfb(coluna) -%}
try_strptime(nullif({{ texto(coluna) }}, '00000000'), '%Y%m%d')::date
{%- endmacro %}

{#- Receita (CNPJ): vírgula decimal sem separador de milhar ("1000,00") -#}
{% macro numero_rfb(coluna) -%}
{{ numero("replace(" ~ texto(coluna) ~ ", ',', '.')") }}
{%- endmacro %}
