{#- Arquivos do site público (spec do site, seção 4). -#}

{#- Um alerta no formato comum do site (seção 4.3), a partir de uma linha de `site_alertas`. -#}
{% macro site_alerta_json() -%}
{
    'alerta_id': alerta_id,
    'tipo': tipo,
    'data': data_fato,
    'valor': valor,
    'parlamentar_id': parlamentar_id,
    'parlamentar_nome': parlamentar_nome,
    'cnpj_raiz': cnpj_raiz,
    'empresa_nome': empresa_nome,
    'cnpj_raiz_2': cnpj_raiz_2,
    'empresa_nome_2': empresa_nome_2,
    'descricao': descricao,
    'correspondencia': correspondencia,
    'regra': regra
}
{%- endmacro %}

{#- Ordem dos alertas em todas as listas do site: do mais recente ao mais antigo. -#}
{% macro site_ordem_alertas() -%}
data_fato desc nulls last, alerta_id
{%- endmacro %}

{% macro site_data(coluna) -%}
strftime({{ coluna }}, '%d/%m/%Y')
{%- endmacro %}

{#- Instante em UTC no formato ISO 8601 (`2026-10-07T10:00:00Z`). -#}
{% macro site_instante(coluna) -%}
strftime({{ coluna }} at time zone 'UTC', '%Y-%m-%dT%H:%M:%SZ')
{%- endmacro %}

{#- Frase dos alertas de sanção: "<prefixo> sancionado no CEIS por <órgão> desde <data>". -#}
{% macro site_sancao(prefixo) -%}
concat(
    {{ prefixo }}, ' sancionado no ', cadastro, ' por ' || orgao_sancionador,
    ' desde ' || {{ site_data('sancao_data_inicio') }}
)
{%- endmacro %}

{% macro site_origem(coluna) -%}
case {{ coluna }}
    when 'cota' then 'Despesa de cota'
    when 'emenda' then 'Pagamento de emenda'
    else 'Contrato'
end
{%- endmacro %}
