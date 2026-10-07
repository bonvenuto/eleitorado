-- Todos os arquivos do site (`caminho` relativo a `site/`, `conteudo` em JSON), que o
-- `coletor site` valida e grava (spec do site, seções 4 e 5).
select caminho, conteudo from {{ ref('site_arquivos_resumo') }}
union all
select caminho, conteudo from {{ ref('site_arquivos_busca') }}
union all
select caminho, conteudo from {{ ref('site_arquivos_parlamentar') }}
union all
select caminho, conteudo from {{ ref('site_arquivos_empresa') }}
union all
select caminho, conteudo from {{ ref('site_arquivos_alertas') }}
