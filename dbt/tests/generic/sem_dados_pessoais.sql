{#-
    LGPD (onda C1): o mart público não pode ter coluna de endereço, contato ou sócio pessoa física
    (nome ou documento de sócio, CPF). Esses dados ficam só no lago privado. Falha com o nome de
    cada coluna proibida encontrada.
-#}
{% test sem_dados_pessoais(model) %}
{%- set proibidas = [
    'tipo_logradouro', 'logradouro', 'numero', 'complemento', 'bairro', 'cep',
    'ddd_1', 'telefone_1', 'ddd_2', 'telefone_2', 'ddd_fax', 'fax', 'correio_eletronico',
] -%}
{%- set achadas = [] -%}
{%- for coluna in adapter.get_columns_in_relation(model) -%}
    {%- set nome = coluna.name | lower -%}
    {%- if nome in proibidas or 'socio_nome' in nome or 'nome_socio' in nome
        or 'documento_socio' in nome or 'cpf' in nome -%}
        {%- do achadas.append(nome) -%}
    {%- endif -%}
{%- endfor -%}

{%- for nome in achadas %}
select '{{ nome }}' as coluna
{% if not loop.last %}union all{% endif %}
{%- else %}
select cast(null as varchar) as coluna from (select 1) where false
{%- endfor %}
{% endtest %}
