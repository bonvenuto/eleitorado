-- Tabelas de apoio da Receita (código e descrição), todas juntas e identificadas por `tabela`.
{%- set tabelas = ['cnaes', 'municipios', 'naturezas', 'qualificacoes', 'motivos', 'paises'] %}
{% for tabela in tabelas %}
select
    '{{ tabela }}' as tabela,
    _competencia as competencia,
    {{ texto('codigo') }} as codigo,
    {{ texto('descricao') }} as descricao
from {{ source('raw_rfb', tabela) }}
{% if not loop.last %}union all{% endif %}
{%- endfor %}
