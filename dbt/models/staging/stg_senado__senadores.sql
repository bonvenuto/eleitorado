-- Senadores com mandato da 53ª legislatura em diante, em todas as datas de referência.
-- `Mandatos.Mandato` vem como lista ou, quando há um só mandato, como objeto.
with origem as (
    select * from {{ fonte_snapshot('senado', 'senadores') }}
),

com_mandatos as (
    select
        *,
        if(
            starts_with(trim(json_query(payload, '$.Mandatos.Mandato')), '['),
            json_query_array(payload, '$.Mandatos.Mandato'),
            [json_query(payload, '$.Mandatos.Mandato')]
        ) as mandatos
    from origem
)

select
    _coleta_id,
    _competencia_data as data_referencia,
    json_value(payload, '$.IdentificacaoParlamentar.CodigoParlamentar') as id_senador,
    json_value(payload, '$.IdentificacaoParlamentar.NomeParlamentar') as nome,
    json_value(payload, '$.IdentificacaoParlamentar.NomeCompletoParlamentar') as nome_completo,
    json_value(payload, '$.IdentificacaoParlamentar.SexoParlamentar') as sexo,
    json_value(payload, '$.IdentificacaoParlamentar.SiglaPartidoParlamentar') as partido_sigla,
    json_value(payload, '$.IdentificacaoParlamentar.UrlFotoParlamentar') as url_foto,
    -- UF do mandato mais recente
    (
        select json_value(mandato, '$.UfParlamentar')
        from unnest(mandatos) as mandato
        order by coalesce(
            safe_cast(json_value(mandato, '$.SegundaLegislaturaDoMandato.NumeroLegislatura') as int64),
            safe_cast(json_value(mandato, '$.PrimeiraLegislaturaDoMandato.NumeroLegislatura') as int64)
        ) desc
        limit 1
    ) as uf_sigla,
    array(
        select distinct legislatura
        from unnest(mandatos) as mandato,
            unnest([
                safe_cast(json_value(mandato, '$.PrimeiraLegislaturaDoMandato.NumeroLegislatura') as int64),
                safe_cast(json_value(mandato, '$.SegundaLegislaturaDoMandato.NumeroLegislatura') as int64)
            ]) as legislatura
        where legislatura is not null
        order by legislatura
    ) as legislaturas
from com_mandatos
