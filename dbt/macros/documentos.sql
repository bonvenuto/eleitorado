{#- Documentos (CPF e CNPJ). Desde 31/07/2026 o CNPJ pode ser alfanumérico: 12 posições com
    dígitos ou letras maiúsculas e 2 dígitos verificadores, calculados por módulo 11 com cada
    caractere valendo seu código ASCII menos 48. -#}

{% macro normalizar_documento(coluna) -%}
nullif(upper(regexp_replace(coalesce({{ coluna }}, ''), r'[^0-9A-Za-z]', '')), '')
{%- endmacro %}

{% macro tipo_documento(doc) -%}
case
    when {{ doc }} is null then null
    when regexp_contains({{ doc }}, r'^[0-9]{11}$') then 'CPF'
    when regexp_contains({{ doc }}, r'^[0-9A-Z]{12}[0-9]{2}$') then 'CNPJ'
    else 'INVALIDO'
end
{%- endmacro %}

{#- dígito verificador por módulo 11: resto < 2 vale 0, senão 11 - resto -#}
{% macro _dv_mod11(doc, pesos) -%}
(
    select if(mod(sum((ascii(substr({{ doc }}, posicao + 1, 1)) - 48) * peso), 11) < 2, 0,
              11 - mod(sum((ascii(substr({{ doc }}, posicao + 1, 1)) - 48) * peso), 11))
    from unnest({{ pesos }}) as peso with offset as posicao
)
{%- endmacro %}

{% macro documento_valido(doc) -%}
case {{ tipo_documento(doc) }}
    when 'CPF' then
        {{ doc }} != repeat(substr({{ doc }}, 1, 1), 11)
        and {{ _dv_mod11(doc, '[10, 9, 8, 7, 6, 5, 4, 3, 2]') }} = cast(substr({{ doc }}, 10, 1) as int64)
        and {{ _dv_mod11(doc, '[11, 10, 9, 8, 7, 6, 5, 4, 3, 2]') }} = cast(substr({{ doc }}, 11, 1) as int64)
    when 'CNPJ' then
        {{ _dv_mod11(doc, '[5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]') }} = cast(substr({{ doc }}, 13, 1) as int64)
        and {{ _dv_mod11(doc, '[6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]') }} = cast(substr({{ doc }}, 14, 1) as int64)
    when 'INVALIDO' then false
end
{%- endmacro %}

{% macro mascarar_cpf(doc) -%}
concat('***.', substr({{ doc }}, 4, 3), '.', substr({{ doc }}, 7, 3), '-**')
{%- endmacro %}

{#- documento que pode ir para os marts: CPF sempre mascarado -#}
{% macro documento_publico(doc) -%}
case
    when {{ tipo_documento(doc) }} = 'CPF' then {{ mascarar_cpf(doc) }}
    -- 9 ou 10 dígitos: provável CPF que perdeu os zeros à esquerda
    when regexp_contains({{ doc }}, r'^[0-9]{9,10}$') then {{ mascarar_cpf("lpad(" ~ doc ~ ", 11, '0')") }}
    else {{ doc }}
end
{%- endmacro %}

{% macro cnpj_raiz(doc) -%}
if({{ tipo_documento(doc) }} = 'CNPJ', substr({{ doc }}, 1, 8), null)
{%- endmacro %}

{#- CPF dentro de texto livre (razão social de MEI traz "NOME 12345678909"): mascara qualquer
    sequência de 11 dígitos isolada, com ou sem pontuação, válida ou não. Aplicada duas vezes
    porque o RE2 não sobrepõe ocorrências que dividem o separador. -#}
{% macro mascarar_cpfs_em_texto(coluna) -%}
regexp_replace(
    regexp_replace(
        {{ coluna }},
        r'(^|[^0-9])[0-9]{3}\.?([0-9]{3})\.?([0-9]{3})-?[0-9]{2}([^0-9]|$)', r'\1***.\2.\3-**\4'
    ),
    r'(^|[^0-9])[0-9]{3}\.?([0-9]{3})\.?([0-9]{3})-?[0-9]{2}([^0-9]|$)', r'\1***.\2.\3-**\4'
)
{%- endmacro %}
