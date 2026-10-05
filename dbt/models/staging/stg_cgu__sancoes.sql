-- CEIS e CNEP num só formato, com todas as datas de referência do raw (60 dias) ou do replay.
-- Vírgula decimal e datas dd/mm/aaaa. O CPF de pessoa física vem completo.
{% set cadastros = ['ceis', 'cnep'] %}

with unidas as (
    {% for cadastro in cadastros %}
    select
        _coleta_id,
        _competencia_data as data_referencia,
        '{{ cadastro | upper }}' as cadastro,
        concat('{{ cadastro }}:', {{ texto('codigo_da_sancao') }}) as sancao_id,
        {{ texto('tipo_de_pessoa') }} as tipo_pessoa,
        {{ normalizar_documento('cpf_ou_cnpj_do_sancionado') }} as documento,
        {{ texto('nome_do_sancionado') }} as nome_sancionado,
        {{ texto('razao_social_cadastro_receita') }} as razao_social_receita,
        {{ texto('categoria_da_sancao') }} as categoria,
        {% if cadastro == 'cnep' %}{{ numero_br('valor_da_multa') }}{% else %}cast(null as numeric){% endif %} as valor_multa,
        {{ data_br('data_inicio_sancao') }} as data_inicio,
        {{ data_br('data_final_sancao') }} as data_fim,
        {{ data_br('data_publicacao') }} as data_publicacao,
        {{ data_br('data_do_transito_em_julgado') }} as data_transito_julgado,
        {{ texto('abragencia_da_sancao') }} as abrangencia,
        {{ texto('orgao_sancionador') }} as orgao_sancionador,
        {{ texto('uf_orgao_sancionador') }} as uf_orgao_sancionador,
        {{ texto('esfera_orgao_sancionador') }} as esfera_orgao_sancionador,
        {{ texto('fundamentacao_legal') }} as fundamentacao_legal,
        {{ texto('numero_do_processo') }} as numero_processo
    from {{ fonte_snapshot('cgu', cadastro) }}
    {% if not loop.last %}union all{% endif %}
    {% endfor %}
)

select
    *,
    -- muda quando qualquer atributo da sanção muda (base do histórico)
    md5(to_json(struct_pack(
        tipo_pessoa, documento, nome_sancionado, razao_social_receita, categoria, valor_multa,
        data_inicio, data_fim, data_publicacao, data_transito_julgado, abrangencia,
        orgao_sancionador, uf_orgao_sancionador, esfera_orgao_sancionador, fundamentacao_legal,
        numero_processo
    ))) as hash_atributos
from unidas
