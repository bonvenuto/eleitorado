{#-
    Histórico por eventos a partir de snapshots completos (seção 7.4 da spec).

    Compara cada data de referência nova com a anterior e com o estado vigente já gravado
    em {{ this }}, e emite um evento por mudança:
      inclusao   - a chave aparece (ou reaparece depois de uma exclusão)
      alteracao  - a chave continua, mas o hash dos atributos mudou
      exclusao   - a chave deixou de aparecer; o evento guarda os últimos atributos

    O tempo do histórico é a data de referência da publicação, nunca o horário da execução.
    Uma data já processada e sem mudanças volta a ser comparada na próxima execução sem gerar
    eventos, então reprocessar é seguro.

    origem: relação com uma linha por (chave, data_referencia), as colunas de `atributos`,
            `hash_atributos` e `_coleta_id`.
-#}
{% macro eventos_de_snapshots(origem, chave, atributos) -%}

with novos as (
    select * from {{ origem }}
    {% if is_incremental() %}
    where data_referencia > (select coalesce(max(data_evento), date '1900-01-01') from {{ this }})
    {% endif %}
),

presencas as (
    select
        {{ chave }},
        data_referencia,
        struct(
            hash_atributos, _coleta_id,
            {% for atributo in atributos %}{{ atributo }}{% if not loop.last %}, {% endif %}{% endfor %}
        ) as estado
    from novos
    {% if is_incremental() %}
    union all
    -- estado vigente já gravado, como se fosse um snapshot anterior a todas as datas novas;
    -- uma chave cuja última versão é exclusão conta como ausente
    select
        {{ chave }},
        date '0001-01-01' as data_referencia,
        struct(
            hash_atributos, _coleta_id,
            {% for atributo in atributos %}{{ atributo }}{% if not loop.last %}, {% endif %}{% endfor %}
        ) as estado
    from {{ this }}
    where true
    qualify row_number() over (partition by {{ chave }} order by data_evento desc) = 1
        and evento != 'exclusao'
    {% endif %}
),

datas as (
    select distinct data_referencia from presencas
),

chaves as (
    select distinct {{ chave }} from presencas
),

grade as (
    select c.{{ chave }}, d.data_referencia, p.estado
    from chaves as c
    cross join datas as d
    left join presencas as p
        on p.{{ chave }} = c.{{ chave }} and p.data_referencia = d.data_referencia
),

comparada as (
    select
        {{ chave }},
        data_referencia,
        estado is not null as presente,
        coalesce(lag(estado is not null) over janela, false) as presente_antes,
        estado.hash_atributos as hash_agora,
        lag(estado.hash_atributos) over janela as hash_antes,
        -- o próprio estado quando presente; o último estado conhecido quando ausente
        last_value(estado ignore nulls) over (
            janela rows between unbounded preceding and current row
        ) as ultimo_estado
    from grade
    window janela as (partition by {{ chave }} order by data_referencia)
),

eventos as (
    select
        *,
        case
            when presente and not presente_antes then 'inclusao'
            when presente and hash_agora != hash_antes then 'alteracao'
            when not presente and presente_antes then 'exclusao'
        end as evento
    from comparada
    where data_referencia > date '0001-01-01'
)

select
    to_hex(md5(concat({{ chave }}, '|', cast(data_referencia as string), '|', evento))) as evento_id,
    {{ chave }},
    data_referencia as data_evento,
    evento,
    ultimo_estado.hash_atributos,
    ultimo_estado._coleta_id,
    {% for atributo in atributos %}
    ultimo_estado.{{ atributo }}{% if not loop.last %},{% endif %}
    {% endfor %}
from eventos
where evento is not null

{%- endmacro %}
