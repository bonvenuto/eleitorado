{# Fontes TSE sempre enumeradas: jamais expandir raw por glob. #}
{% macro fonte_tse(familia) -%}
  {% set familias = ['candidaturas', 'bens', 'receitas', 'contratadas', 'pagamentos',
                     'doador_originario'] %}
  {% if familia not in familias %}
    {{ exceptions.raise_compiler_error('Família TSE desconhecida') }}
  {% endif %}
  {% set fontes = var('tse_fontes', none) %}
  {% if fontes is none and target.name == 'ci' %}
    {% set fontes = {familia: [env_var('ELEITORADO_LAGO', 'dbt/tests/lago_vazio')
        ~ '/estado/tse/ci/' ~ familia ~ '/vazio/vazio.parquet']} %}
  {% endif %}
  {% if fontes is not mapping or familia not in fontes %}
    {{ exceptions.raise_compiler_error('Execução TSE exige fontes explícitas') }}
  {% endif %}
  {% set arquivos = fontes[familia] %}
  {% if arquivos is string or arquivos is not sequence or arquivos | length == 0 %}
    {{ exceptions.raise_compiler_error('Família TSE exige lista não vazia de arquivos') }}
  {% endif %}
  {% set literais = [] %}
  {% for arquivo in arquivos %}
    {% if arquivo is not string or not arquivo.endswith('.parquet') or '*' in arquivo
          or '?' in arquivo or '[' in arquivo or ']' in arquivo %}
      {{ exceptions.raise_compiler_error('Arquivo TSE deve ser explícito, sem glob') }}
    {% endif %}
    {% do literais.append("'" ~ arquivo.replace("'", "''") ~ "'") %}
  {% endfor %}
  read_parquet([{{ literais | join(', ') }}], union_by_name = true, hive_partitioning = false)
{%- endmacro %}

{%- macro tse_saida_mart(nome) -%}
  {%- if not nome or '/' in nome or '\\' in nome or '..' in nome or ':' in nome -%}
    {{ exceptions.raise_compiler_error('Nome de mart TSE inválido') }}
  {%- endif -%}
  {%- set saida = var('tse_saida', none) -%}
  {%- if saida is none and target.name == 'ci' -%}
    {%- set saida = env_var('ELEITORADO_LAGO', 'dbt/tests/lago_vazio') ~ '/estado/tse/ci/marts' -%}
  {%- endif -%}
  {%- if saida is not string or not saida -%}
    {{ exceptions.raise_compiler_error('Execução TSE exige saída privada explícita') }}
  {%- endif -%}
  {{- saida ~ '/' ~ nome ~ '.parquet' -}}
{%- endmacro -%}
