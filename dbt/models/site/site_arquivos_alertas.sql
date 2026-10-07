-- Alertas de cada tipo em páginas de `site_alertas_por_pagina` (`alertas/<tipo>/<n>.json`, spec do
-- site, seção 4.2), do mais recente ao mais antigo. Tipo sem alerta não tem arquivo (o
-- `resumo.json` traz a quantidade 0).
with numerados as (
    select
        *,
        (row_number() over (partition by tipo order by {{ site_ordem_alertas() }}) - 1)
            // {{ var('site_alertas_por_pagina') }} + 1 as pagina,
        count(*) over (partition by tipo) as total
    from {{ ref('site_alertas') }}
)

select
    'alertas/' || tipo || '/' || pagina || '.json' as caminho,
    to_json({
        'esquema': 1,
        'tipo': tipo,
        'pagina': pagina,
        'paginas': cast(ceil(any_value(total) / {{ var('site_alertas_por_pagina') }}) as bigint),
        'total': any_value(total),
        'alertas': list({{ site_alerta_json() }} order by {{ site_ordem_alertas() }})
    })::varchar as conteudo
from numerados
group by tipo, pagina
