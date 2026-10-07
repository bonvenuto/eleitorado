-- Uma linha por empresa (raiz do CNPJ) na competência mais recente da Receita: cadastro, matriz,
-- Simples/MEI e contagens. A data de abertura é o início de atividade mais antigo entre os
-- estabelecimentos: quando a matriz muda, a nova tem data recente.
with codigos as (
    select * from {{ ref('stg_rfb__codigos') }}
    where competencia = (select max(competencia) from {{ ref('stg_rfb__codigos') }})
),

estabelecimentos as (
    select
        cnpj_raiz,
        count(*) as estabelecimentos,
        min(data_inicio_atividade) as data_abertura
    from {{ ref('int_rfb__estabelecimentos') }}
    group by cnpj_raiz
),

matriz as (
    select * from {{ ref('int_rfb__estabelecimentos') }}
    where matriz
    qualify row_number() over (partition by cnpj_raiz order by cnpj) = 1
),

socios as (
    select cnpj_raiz, count(*) as socios from {{ ref('int_rfb__socios') }} group by cnpj_raiz
),

simples as (
    select * from {{ ref('stg_rfb__simples') }}
    where competencia = (select max(competencia) from {{ ref('stg_rfb__simples') }})
)

select
    e.cnpj_raiz,
    e.razao_social,
    e.natureza_juridica_codigo,
    n.descricao as natureza_juridica,
    e.qualificacao_responsavel_codigo,
    e.capital_social,
    e.porte_codigo,
    case e.porte_codigo
        when '00' then 'NAO INFORMADO'
        when '01' then 'MICRO EMPRESA'
        when '03' then 'EMPRESA DE PEQUENO PORTE'
        when '05' then 'DEMAIS'
    end as porte,
    e.ente_federativo_responsavel,
    est.data_abertura,
    m.cnpj as matriz_cnpj,
    m.nome_fantasia,
    m.situacao_codigo,
    m.situacao,
    m.data_situacao,
    m.motivo_codigo,
    m.motivo,
    m.cnae_principal,
    m.cnae_principal_descricao,
    m.municipio_id,
    m.uf_sigla,
    coalesce(s.optante_simples, false) as optante_simples,
    s.data_opcao_simples,
    s.data_exclusao_simples,
    coalesce(s.optante_mei, false) as optante_mei,
    s.data_opcao_mei,
    s.data_exclusao_mei,
    coalesce(est.estabelecimentos, 0) as estabelecimentos,
    coalesce(so.socios, 0) as socios,
    e.competencia as competencia_receita
from {{ ref('stg_rfb__empresas') }} as e
left join codigos as n on n.tabela = 'naturezas' and n.codigo = e.natureza_juridica_codigo
left join estabelecimentos as est on est.cnpj_raiz = e.cnpj_raiz
left join matriz as m on m.cnpj_raiz = e.cnpj_raiz
left join socios as so on so.cnpj_raiz = e.cnpj_raiz
left join simples as s on s.cnpj_raiz = e.cnpj_raiz
where e.competencia = (select max(competencia) from {{ ref('stg_rfb__empresas') }})
