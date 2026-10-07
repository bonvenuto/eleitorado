-- Dois participantes (raízes diferentes) da mesma licitação do Portal com sócio em comum: sócio
-- empresa pela raiz do CNPJ; sócio pessoa física pelo nome e pelos 6 dígitos visíveis do CPF. O
-- sócio precisa ter entrado nas duas empresas até a data da licitação. Publica o par, quem venceu
-- e as qualificações; nunca o nome nem o CPF de sócio pessoa física. Indício para investigar.
with participantes as (
    select
        licitacao_id,
        participante_cnpj_raiz as cnpj_raiz,
        any_value(licitacao_numero) as licitacao_numero,
        any_value(orgao_nome) as orgao_nome,
        min(data_licitacao) as data_licitacao,
        any_value(participante_nome) as participante_nome,
        bool_or(vencedor) as venceu
    from {{ ref('int_cgu__licitacao_participantes') }}
    where participante_cnpj_raiz is not null and data_licitacao is not null
    group by licitacao_id, participante_cnpj_raiz
),

socios as (
    select
        cnpj_raiz,
        tipo_socio,
        qualificacao,
        data_entrada,
        documento_socio,
        if(
            tipo_socio = 'pessoa_juridica',
            documento_socio,
            concat(nome_socio_normalizado, '|', documento_socio)
        ) as chave
    from {{ ref('int_rfb__socios') }}
    where tipo_socio in ('pessoa_juridica', 'pessoa_fisica') and data_entrada is not null
),

em_comum as (
    select
        a.licitacao_id,
        a.licitacao_numero,
        a.orgao_nome,
        a.data_licitacao,
        a.cnpj_raiz as participante_a_cnpj_raiz,
        a.participante_nome as participante_a_nome,
        a.venceu as participante_a_venceu,
        b.cnpj_raiz as participante_b_cnpj_raiz,
        b.participante_nome as participante_b_nome,
        b.venceu as participante_b_venceu,
        sa.tipo_socio,
        sa.chave,
        sa.qualificacao as qualificacao_a,
        sb.qualificacao as qualificacao_b,
        if(sa.tipo_socio = 'pessoa_juridica', sa.documento_socio, null) as socio_cnpj_raiz
    from participantes as a
    join participantes as b
        on b.licitacao_id = a.licitacao_id and a.cnpj_raiz < b.cnpj_raiz
    join socios as sa
        on sa.cnpj_raiz = a.cnpj_raiz and sa.data_entrada <= a.data_licitacao
    join socios as sb
        on sb.cnpj_raiz = b.cnpj_raiz
        and sb.tipo_socio = sa.tipo_socio
        and sb.chave = sa.chave
        and sb.data_entrada <= a.data_licitacao
)

select
    md5(concat(
        'licitacao_socios_em_comum|', licitacao_id, '|',
        participante_a_cnpj_raiz, '|', participante_b_cnpj_raiz
    )) as alerta_id,
    licitacao_id,
    licitacao_numero,
    orgao_nome,
    data_licitacao,
    participante_a_cnpj_raiz,
    {{ mascarar_cpfs_em_texto('participante_a_nome') }} as participante_a_nome,
    participante_a_venceu,
    participante_b_cnpj_raiz,
    {{ mascarar_cpfs_em_texto('participante_b_nome') }} as participante_b_nome,
    participante_b_venceu,
    count(distinct chave) filter (where tipo_socio = 'pessoa_fisica') as socios_pessoa_fisica,
    count(distinct chave) filter (where tipo_socio = 'pessoa_juridica') as socios_empresa,
    list(distinct socio_cnpj_raiz order by socio_cnpj_raiz)
        filter (where socio_cnpj_raiz is not null) as socios_empresa_cnpj_raiz,
    list(distinct qualificacao_a order by qualificacao_a)
        filter (where qualificacao_a is not null) as qualificacoes_no_participante_a,
    list(distinct qualificacao_b order by qualificacao_b)
        filter (where qualificacao_b is not null) as qualificacoes_no_participante_b,
    'Participantes de raízes diferentes na mesma licitação com sócio em comum desde antes da '
    || 'licitação (empresa pela raiz do CNPJ; pessoa física por nome e 6 dígitos do CPF)' as regra
from em_comum
group by all
