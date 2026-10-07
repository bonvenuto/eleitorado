-- Parlamentar que é sócio (pessoa física) de empresa que aparece nos dados do eleitorado.
-- Deputado: mesmo nome civil e mesmos 6 dígitos do meio do CPF (`nome e cpf`). Senador: só pelo
-- nome completo (`só nome`), sujeito a homônimo. Traz o que a empresa recebeu da cota do próprio
-- parlamentar, de emendas de autoria dele e em contratos federais. O CPF não aparece.
with deputados as (
    select
        concat('camara:', id_deputado) as parlamentar_id,
        {{ nome_normalizado('nome_civil') }} as nome,
        substr(cpf, 4, 6) as cpf_meio,
        'nome e cpf' as correspondencia
    from {{ ref('stg_camara__deputados_detalhe') }}
    where nome_civil is not null and length(cpf) = 11
    qualify row_number() over (partition by id_deputado order by data_referencia desc) = 1
),

senadores as (
    select distinct
        concat('senado:', id_senador) as parlamentar_id,
        {{ nome_normalizado('nome_completo') }} as nome,
        cast(null as varchar) as cpf_meio,
        'só nome' as correspondencia
    from {{ ref('stg_senado__senadores') }}
    where nome_completo is not null
),

parlamentares as (
    select * from deputados
    union all
    select * from senadores
),

vinculos as (
    select
        p.parlamentar_id,
        p.correspondencia,
        s.cnpj_raiz,
        list(distinct s.qualificacao order by s.qualificacao) as qualificacoes,
        min(s.data_entrada) as data_entrada
    from parlamentares as p
    join {{ ref('int_rfb__socios') }} as s
        on s.tipo_socio = 'pessoa_fisica'
        and s.nome_socio_normalizado = p.nome
        and (p.cpf_meio is null or substr(s.documento_socio, 4, 6) = p.cpf_meio)
    group by all
),

fatos as (
    {{ rfb_fatos() }}
),

totais as (
    select
        v.parlamentar_id,
        v.cnpj_raiz,
        coalesce(sum(f.valor) filter (
            where f.origem = 'cota' and f.parlamentar_id = v.parlamentar_id
        ), 0) as cota_do_parlamentar,
        coalesce(sum(f.valor) filter (
            where f.origem = 'emenda' and f.parlamentar_id = v.parlamentar_id
        ), 0) as emendas_do_parlamentar,
        coalesce(sum(f.valor) filter (where f.origem = 'contrato'), 0) as contratos_federais
    from vinculos as v
    left join fatos as f on f.cnpj_raiz = v.cnpj_raiz
    group by v.parlamentar_id, v.cnpj_raiz
)

select
    md5(concat('parlamentar_socio_fornecedor|', v.parlamentar_id, '|', v.cnpj_raiz)) as alerta_id,
    v.parlamentar_id,
    dp.nome as parlamentar_nome,
    v.correspondencia,
    v.cnpj_raiz,
    {{ mascarar_cpfs_em_texto('e.razao_social') }} as razao_social,
    e.situacao,
    v.qualificacoes,
    v.data_entrada,
    t.cota_do_parlamentar,
    t.emendas_do_parlamentar,
    t.contratos_federais,
    'Sócio pessoa física com o nome civil e os 6 dígitos do meio do CPF do deputado, ou com o '
    || 'nome completo do senador' as regra
from vinculos as v
join totais as t on t.parlamentar_id = v.parlamentar_id and t.cnpj_raiz = v.cnpj_raiz
left join {{ ref('int_rfb__empresas') }} as e on e.cnpj_raiz = v.cnpj_raiz
left join {{ ref('dim_parlamentar') }} as dp on dp.parlamentar_id = v.parlamentar_id
