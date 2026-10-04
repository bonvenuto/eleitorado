{{ config(materialized='view') }}

-- Câmara e Senado num só cadastro, uma linha por parlamentar na data de referência.
-- Na Câmara, nome, UF e partido vêm da legislatura mais recente do deputado.
with deputados as (
    select
        concat('camara:', id_deputado) as parlamentar_id,
        'camara' as casa,
        id_deputado as id_origem,
        data_referencia,
        _coleta_id,
        array_agg(
            struct(nome, uf_sigla, partido_sigla, url_foto)
            order by legislatura desc limit 1
        )[offset(0)] as recente,
        array_agg(distinct legislatura order by legislatura) as legislaturas
    from {{ ref('stg_camara__deputados') }}
    group by 1, 2, 3, 4, 5
),

unidos as (
    select
        parlamentar_id, casa, id_origem, data_referencia, _coleta_id,
        recente.nome, recente.uf_sigla, recente.partido_sigla, recente.url_foto, legislaturas
    from deputados
    union all
    select
        concat('senado:', id_senador), 'senado', id_senador, data_referencia, _coleta_id,
        nome, uf_sigla, partido_sigla, url_foto, legislaturas
    from {{ ref('stg_senado__senadores') }}
)

select
    *,
    to_hex(md5(to_json_string(struct(casa, nome, uf_sigla, partido_sigla)))) as hash_atributos
from unidos
