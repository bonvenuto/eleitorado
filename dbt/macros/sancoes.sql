{#- Chave de correspondência com as sanções: CPF completo para pessoa física, raiz do CNPJ para
    pessoa jurídica (matriz e filiais são a mesma pessoa jurídica). Um join por igualdade, sem OR. -#}
{% macro chave_correspondencia(tipo, documento) -%}
case {{ tipo }}
    when 'CPF' then 'cpf:' || {{ documento }}
    when 'CNPJ' then 'cnpj:' || substr({{ documento }}, 1, 8)
end
{%- endmacro %}

{#- Qualquer versão já vista de cada sanção (exclusões não são versões), com a chave de
    correspondência. Corpo de uma CTE. -#}
{% macro sancoes_para_alerta() -%}
select distinct
    sancao_id, cadastro, tipo_pessoa, documento, nome_sancionado, categoria, abrangencia,
    orgao_sancionador, data_inicio, data_fim, _coleta_id, data_evento,
    {{ chave_correspondencia(tipo_documento('documento'), 'documento') }} as chave
from {{ ref('int_cgu__sancoes_eventos') }}
where evento != 'exclusao' and data_inicio is not null
{%- endmacro %}

{#- Tipo de correspondência para a coluna de mesmo nome dos alertas -#}
{% macro tipo_correspondencia(tipo, documento, documento_sancao) -%}
case
    when {{ tipo }} = 'CPF' then 'cpf'
    when {{ documento }} = {{ documento_sancao }} then 'cnpj'
    else 'cnpj_raiz'
end
{%- endmacro %}
