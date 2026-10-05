-- Senadores com mandato da 53ª legislatura em diante, em todas as datas de referência.
-- `Mandatos.Mandato` vem como lista ou, quando há um só mandato, como objeto.
with origem as (
    select * from {{ fonte_snapshot('senado', 'senadores') }}
),

com_mandatos as (
    select
        *,
        if(
            json_type(json_extract(payload, '$.Mandatos.Mandato')) = 'ARRAY',
            json_extract(payload, '$.Mandatos.Mandato[*]'),
            [json_extract(payload, '$.Mandatos.Mandato')]
        ) as mandatos
    from origem
)

select
    _coleta_id,
    _competencia_data as data_referencia,
    json_extract_string(payload, '$.IdentificacaoParlamentar.CodigoParlamentar') as id_senador,
    json_extract_string(payload, '$.IdentificacaoParlamentar.NomeParlamentar') as nome,
    json_extract_string(payload, '$.IdentificacaoParlamentar.NomeCompletoParlamentar') as nome_completo,
    json_extract_string(payload, '$.IdentificacaoParlamentar.SexoParlamentar') as sexo,
    json_extract_string(payload, '$.IdentificacaoParlamentar.SiglaPartidoParlamentar') as partido_sigla,
    json_extract_string(payload, '$.IdentificacaoParlamentar.UrlFotoParlamentar') as url_foto,
    -- UF do mandato mais recente
    (
        select json_extract_string(mandato, '$.UfParlamentar')
        from unnest(mandatos) as u(mandato)
        order by coalesce(
            try_cast(json_extract_string(mandato, '$.SegundaLegislaturaDoMandato.NumeroLegislatura') as bigint),
            try_cast(json_extract_string(mandato, '$.PrimeiraLegislaturaDoMandato.NumeroLegislatura') as bigint)
        ) desc
        limit 1
    ) as uf_sigla,
    array(
        select distinct legislatura
        from unnest(mandatos) as u(mandato),
            unnest([
                try_cast(json_extract_string(mandato, '$.PrimeiraLegislaturaDoMandato.NumeroLegislatura') as bigint),
                try_cast(json_extract_string(mandato, '$.SegundaLegislaturaDoMandato.NumeroLegislatura') as bigint)
            ]) as l(legislatura)
        where legislatura is not null
        order by legislatura
    ) as legislaturas
from com_mandatos
