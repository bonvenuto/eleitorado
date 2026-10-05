{#-
    LGPD (seção 7.6 da spec): nenhuma coluna de texto do modelo pode ter um CPF sem máscara,
    formatado ou não. Percorre todas as colunas VARCHAR, menos as chaves (`*_id`, hashes
    hexadecimais) e as listadas em `excluir` (números de nota, URLs). Falha com cada valor
    encontrado, para dar para corrigir na origem.
-#}
{% test sem_cpf_completo(model, excluir=[]) %}
{%- set colunas = [] -%}
{%- for coluna in adapter.get_columns_in_relation(model) -%}
    {%- if coluna.dtype == 'VARCHAR' and not coluna.name.endswith('_id')
        and coluna.name not in excluir -%}
        {%- do colunas.append(coluna.name) -%}
    {%- endif -%}
{%- endfor -%}

{%- for coluna in colunas %}
select '{{ coluna }}' as coluna, {{ coluna }} as valor
from {{ model }}
where regexp_matches({{ coluna }}, '(^|[^0-9])[0-9]{3}\.?[0-9]{3}\.?[0-9]{3}-?[0-9]{2}([^0-9]|$)')
{% if not loop.last %}union all{% endif %}
{%- else %}
select cast(null as varchar) as coluna, cast(null as varchar) as valor
from (select 1) where false
{%- endfor %}
{% endtest %}
