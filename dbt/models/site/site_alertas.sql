-- Os alertas de fatos num formato comum para o site (spec do site, seção 4.3). Correspondência
-- `fraca`: sanção casada só pela raiz do CNPJ (outra filial) e senador sócio só pelo nome.
-- `alerta_fonte_reduzida` fica de fora: é sobre os dados, não sobre parlamentar ou empresa.
with autores as (
    select autor_codigo, autor_nome, parlamentar_id from {{ ref('dim_autor_emenda') }}
),

alertas as (
    select
        alerta_id,
        'cota_fornecedor_sancionado' as tipo,
        data_emissao as data_fato,
        valor_reembolsado as valor,
        parlamentar_id,
        nome_beneficiario as parlamentar_nome,
        {{ cnpj_raiz('fornecedor_documento') }} as cnpj_raiz,
        fornecedor_nome as empresa_nome,
        cast(null as varchar) as cnpj_raiz_2,
        cast(null as varchar) as empresa_nome_2,
        {{ site_sancao("'Despesa de cota com fornecedor'") }} as descricao,
        if(tipo_correspondencia = 'cnpj_raiz', 'fraca', 'forte') as correspondencia,
        regra
    from {{ ref('alerta_cota_fornecedor_sancionado') }}

    union all
    select
        alerta_id,
        'cota_documento_invalido',
        data_emissao,
        valor_reembolsado,
        parlamentar_id,
        nome_beneficiario,
        null,
        fornecedor_nome,
        null,
        null,
        concat(
            'Despesa de cota com documento de fornecedor inválido (',
            if(motivo = 'tamanho', 'tamanho', 'dígito verificador'), ')'
        ),
        'forte',
        regra
    from {{ ref('alerta_cota_documento_invalido') }}

    union all
    select
        x.alerta_id,
        'emenda_favorecido_sancionado',
        x.data_documento,
        x.valor_pago,
        a.parlamentar_id,
        a.autor_nome,
        {{ cnpj_raiz('x.favorecido_documento') }},
        x.favorecido_nome,
        null,
        null,
        {{ site_sancao("x.fase_despesa || ' de emenda a favorecido'") }},
        if(x.tipo_correspondencia = 'cnpj_raiz', 'fraca', 'forte'),
        x.regra
    from {{ ref('alerta_emenda_favorecido_sancionado') }} as x
    left join autores as a on a.autor_codigo = x.autor_codigo

    union all
    select
        alerta_id,
        'contrato_fornecedor_sancionado',
        data_assinatura,
        valor_final,
        null,
        null,
        {{ cnpj_raiz('fornecedor_documento') }},
        fornecedor_nome,
        null,
        null,
        {{ site_sancao("concat('Contrato', ' de ' || orgao_nome, ' com fornecedor')") }},
        if(tipo_correspondencia = 'cnpj_raiz', 'fraca', 'forte'),
        regra
    from {{ ref('alerta_contrato_fornecedor_sancionado') }}

    union all
    select
        alerta_id,
        'licitacao_vencedor_sancionado',
        data_licitacao,
        null,
        null,
        null,
        {{ cnpj_raiz('participante_documento') }},
        participante_nome,
        null,
        null,
        {{ site_sancao("concat('Vencedor de licitação', ' de ' || orgao_nome)") }},
        if(tipo_correspondencia = 'cnpj_raiz', 'fraca', 'forte'),
        regra
    from {{ ref('alerta_licitacao_vencedor_sancionado') }}

    union all
    select
        alerta_id,
        'pagamento_empresa_irregular',
        data_fato,
        valor,
        parlamentar_id,
        null,
        {{ cnpj_raiz('cnpj') }},
        razao_social,
        null,
        null,
        concat(
            {{ site_origem('origem') }}, ' com empresa ', lower(situacao), ' na Receita desde ',
            {{ site_data('data_situacao') }}
        ),
        'forte',
        regra
    from {{ ref('alerta_pagamento_empresa_irregular') }}

    union all
    select
        alerta_id,
        'empresa_recem_aberta',
        data_fato,
        valor,
        parlamentar_id,
        null,
        {{ cnpj_raiz('cnpj') }},
        razao_social,
        null,
        null,
        if(
            tipo = 'fato_antes_da_abertura',
            concat(
                {{ site_origem('origem') }}, ' anterior à abertura da empresa (',
                {{ site_data('data_abertura') }}, ')'
            ),
            concat(
                {{ site_origem('origem') }}, ' com empresa aberta ', dias_desde_a_abertura,
                ' dias antes'
            )
        ),
        'forte',
        regra
    from {{ ref('alerta_empresa_recem_aberta') }}

    union all
    select
        alerta_id,
        'licitacao_socios_em_comum',
        data_licitacao,
        null,
        null,
        null,
        participante_a_cnpj_raiz,
        participante_a_nome,
        participante_b_cnpj_raiz,
        participante_b_nome,
        concat(
            'Participantes da mesma licitação', ' de ' || orgao_nome, ' com ',
            coalesce(socios_pessoa_fisica, 0) + coalesce(socios_empresa, 0), ' sócio(s) em comum'
        ),
        'forte',
        regra
    from {{ ref('alerta_licitacao_socios_em_comum') }}

    union all
    select
        alerta_id,
        'parlamentar_socio_fornecedor',
        data_entrada,
        null,
        parlamentar_id,
        parlamentar_nome,
        cnpj_raiz,
        razao_social,
        null,
        null,
        concat('Parlamentar sócio da empresa', ' desde ' || {{ site_data('data_entrada') }}),
        if(correspondencia = 'só nome', 'fraca', 'forte'),
        regra
    from {{ ref('alerta_parlamentar_socio_fornecedor') }}
)

select
    a.alerta_id,
    a.tipo,
    a.data_fato,
    cast(a.valor as decimal(38, 2)) as valor,
    a.parlamentar_id,
    coalesce(a.parlamentar_nome, p.nome) as parlamentar_nome,
    a.cnpj_raiz,
    a.empresa_nome,
    a.cnpj_raiz_2,
    a.empresa_nome_2,
    a.descricao,
    a.correspondencia,
    a.regra
from alertas as a
left join {{ ref('dim_parlamentar') }} as p on p.parlamentar_id = a.parlamentar_id
