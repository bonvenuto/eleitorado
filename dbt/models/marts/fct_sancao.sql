-- Sanções presentes no arquivo mais recente de cada cadastro (CEIS e CNEP).
with sancoes as (
    select *
    from {{ ref('stg_cgu__sancoes') }}
    where true
    qualify data_referencia = max(data_referencia) over (partition by cadastro)
)

select
    sancao_id,
    cadastro,
    data_referencia,
    tipo_pessoa,
    {{ documento_publico('documento') }} as sancionado_documento,
    {{ cnpj_raiz('documento') }} as sancionado_cnpj_raiz,
    {{ mascarar_cpfs_em_texto('nome_sancionado') }} as sancionado_nome,
    {{ mascarar_cpfs_em_texto('razao_social_receita') }} as razao_social_receita,
    categoria,
    valor_multa,
    abrangencia,
    fundamentacao_legal,
    numero_processo,
    data_inicio,
    data_fim,
    data_publicacao,
    data_transito_julgado,
    orgao_sancionador,
    uf_orgao_sancionador,
    esfera_orgao_sancionador,
    _coleta_id
from sancoes
