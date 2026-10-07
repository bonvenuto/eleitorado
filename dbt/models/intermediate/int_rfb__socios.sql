-- Sócios na competência mais recente da Receita, como a Receita publica: CPF de pessoa física
-- mascarado (`***456789**`) e sócio empresa só com a raiz do CNPJ (8 posições). Fica no lago
-- privado; os marts nunca publicam sócio pessoa física.
with qualificacoes as (
    select codigo, descricao from {{ ref('stg_rfb__codigos') }}
    where tabela = 'qualificacoes'
        and competencia = (select max(competencia) from {{ ref('stg_rfb__codigos') }})
)

select
    s.* exclude (competencia),
    s.competencia as competencia_receita,
    case s.tipo_socio_codigo
        when '1' then 'pessoa_juridica'
        when '2' then 'pessoa_fisica'
        when '3' then 'estrangeiro'
    end as tipo_socio,
    {{ nome_normalizado('s.nome_socio') }} as nome_socio_normalizado,
    q.descricao as qualificacao
from {{ ref('stg_rfb__socios') }} as s
left join qualificacoes as q on q.codigo = s.qualificacao_codigo
where s.competencia = (select max(competencia) from {{ ref('stg_rfb__socios') }})
