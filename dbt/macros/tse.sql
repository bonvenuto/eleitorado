{# Fontes TSE enumeradas, enriquecidas somente pelos descritores da seleção fixada. #}
{% macro fonte_tse(familia) -%}
  {% set familias = ['candidaturas', 'bens', 'receitas', 'contratadas', 'pagamentos',
                     'doador_originario'] %}
  {% if familia not in familias %}
    {{ exceptions.raise_compiler_error('Família TSE desconhecida') }}
  {% endif %}
  {% set vazio = env_var('ELEITORADO_LAGO', 'dbt/tests/lago_vazio')
      ~ '/estado/tse/ci/' ~ familia ~ '/vazio/vazio.parquet' %}
  {% set fontes = var('tse_fontes', none) %}
  {% set proveniencia = var('tse_proveniencia', none) %}
  {% if fontes is none and target.name == 'ci' %}
    {% set fontes = {familia: [vazio]} %}
    {% set proveniencia = {vazio: {'ano_arquivo': none, 'versao_id': none, 'layout_id': none}} %}
  {% endif %}
  {% if fontes is not mapping or familia not in fontes %}
    {{ exceptions.raise_compiler_error('Execução TSE exige fontes explícitas') }}
  {% endif %}
  {% set arquivos = fontes[familia] %}
  {% if arquivos is string or arquivos is not sequence or arquivos | length == 0 %}
    {{ exceptions.raise_compiler_error('Família TSE exige lista não vazia de arquivos') }}
  {% endif %}
  {% if proveniencia is not mapping %}
    {{ exceptions.raise_compiler_error('Execução TSE exige proveniência explícita') }}
  {% endif %}
  {% set todos_arquivos = [] %}
  {% for grupo in fontes.values() %}
    {% if grupo is string or grupo is not sequence %}
      {{ exceptions.raise_compiler_error('Família TSE exige lista de arquivos') }}
    {% endif %}
    {% for caminho in grupo %}
      {% if caminho is not string %}
        {{ exceptions.raise_compiler_error('Caminho TSE inválido') }}
      {% endif %}
      {% do todos_arquivos.append(caminho) %}
    {% endfor %}
  {% endfor %}
  {% if proveniencia.keys() | sort != todos_arquivos | sort %}
    {{ exceptions.raise_compiler_error('Proveniência deve corresponder exatamente às fontes') }}
  {% endif %}
  {% set consultas = [] %}
  {% for arquivo in arquivos %}
    {% if arquivo is not string or not arquivo.endswith('.parquet') or '*' in arquivo
          or '?' in arquivo or '[' in arquivo or ']' in arquivo %}
      {{ exceptions.raise_compiler_error('Arquivo TSE deve ser explícito, sem glob') }}
    {% endif %}
    {% set meta = proveniencia.get(arquivo) %}
    {% if meta is not mapping or meta.keys() | sort != ['ano_arquivo', 'layout_id', 'versao_id'] %}
      {{ exceptions.raise_compiler_error('Metadados de proveniência ausentes ou inválidos') }}
    {% endif %}
    {% set bootstrap = arquivo == vazio and meta.ano_arquivo is none
        and meta.versao_id is none and meta.layout_id is none %}
    {% if not bootstrap and (meta.ano_arquivo is not integer or meta.ano_arquivo is boolean
        or meta.ano_arquivo not in [2018, 2020, 2022, 2024]
        or meta.versao_id is not string or meta.versao_id | length != 64
        or meta.layout_id != 'tse:' ~ familia ~ ':' ~ meta.ano_arquivo ~ ':v1') %}
      {{ exceptions.raise_compiler_error('Metadados de proveniência inválidos') }}
    {% endif %}
    {% if not bootstrap %}
      {% for caractere in meta.versao_id %}
        {% if caractere not in '0123456789abcdef' %}
          {{ exceptions.raise_compiler_error('Identidade de versão inválida na proveniência') }}
        {% endif %}
      {% endfor %}
    {% endif %}
    {% set caminho_sql = "'" ~ arquivo.replace("'", "''") ~ "'" %}
    {% set leitura = 'read_parquet(' ~ caminho_sql ~ ', hive_partitioning = false)' %}
    {% if execute %}
      {% set esquema = run_query('describe select * from ' ~ leitura) %}
      {% for coluna in esquema.rows %}
        {% if coluna[0] | lower in ['ano_arquivo', 'versao_id', 'layout_id'] %}
          {{ exceptions.raise_compiler_error('Raw TSE colide com proveniência reservada') }}
        {% endif %}
      {% endfor %}
      {% if bootstrap %}
        {% set contagem = run_query('select count(*) from ' ~ leitura) %}
        {% if contagem.rows[0][0] != 0 %}
          {{ exceptions.raise_compiler_error('Bootstrap TSE exige arquivo vazio conhecido') }}
        {% endif %}
      {% endif %}
    {% endif %}
    {% set ano = 'null' if bootstrap else meta.ano_arquivo | string %}
    {% set versao = 'null' if bootstrap else "'" ~ meta.versao_id.replace("'", "''") ~ "'" %}
    {% set layout = 'null' if bootstrap else "'" ~ meta.layout_id.replace("'", "''") ~ "'" %}
    {% do consultas.append('select *, ' ~ ano ~ '::integer as ano_arquivo, '
        ~ versao ~ '::varchar as versao_id, ' ~ layout ~ '::varchar as layout_id from ' ~ leitura) %}
  {% endfor %}
  ({{ consultas | join(' union all by name ') }})
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
