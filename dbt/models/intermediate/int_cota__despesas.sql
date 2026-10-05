-- CEAP e CEAPS no mesmo grão: uma linha de despesa como publicada.
-- Documento do fornecedor completo (CPF inclusive): esta camada não é exposta à web app.
with camara as (
    select
        -- a CEAP não tem chave natural: hash do conteúdo + ocorrência entre linhas idênticas
        concat(
            'camara:', hash_linha, '-',
            cast(row_number() over (partition by hash_linha order by _competencia, _linha) as varchar)
        ) as despesa_id,
        'camara' as casa,
        if(id_deputado is null, null, concat('camara:', id_deputado)) as parlamentar_id,
        if(id_deputado is null, 'lideranca', 'parlamentar') as tipo_beneficiario,
        nome_beneficiario,
        nullif(uf_sigla, 'NA') as uf_sigla,  -- lideranças vêm com `NA`
        partido_sigla,
        ano,
        mes,
        data_emissao,
        categoria,
        subcategoria,
        fornecedor_nome,
        fornecedor_documento,
        cast(null as varchar) as fornecedor_documento_mascarado,
        valor_documento,
        valor_glosa,
        valor_reembolsado,
        numero_documento,
        url_documento,
        id_documento_origem,
        passageiro as camara_passageiro,
        trecho as camara_trecho,
        cast(null as varchar) as senado_detalhamento,
        _coleta_id
    from {{ ref('stg_camara__ceap') }}
),

senado as (
    select
        concat('senado:', c.id_despesa) as despesa_id,
        'senado' as casa,
        concat('senado:', c.id_senador) as parlamentar_id,
        'parlamentar' as tipo_beneficiario,
        c.nome_senador as nome_beneficiario,
        s.uf_sigla,
        cast(null as varchar) as partido_sigla,
        c.ano,
        c.mes,
        c.data_emissao,
        c.categoria,
        c.tipo_documento_fiscal as subcategoria,
        c.fornecedor_nome,
        c.fornecedor_documento,
        c.fornecedor_documento_mascarado,
        cast(null as decimal(38, 2)) as valor_documento,
        cast(null as decimal(38, 2)) as valor_glosa,
        c.valor_reembolsado,
        c.numero_documento,
        cast(null as varchar) as url_documento,
        c.id_despesa as id_documento_origem,
        cast(null as varchar) as camara_passageiro,
        cast(null as varchar) as camara_trecho,
        c.detalhamento as senado_detalhamento,
        c._coleta_id
    from {{ ref('stg_senado__ceaps') }} as c
    left join (
        select id_senador, uf_sigla
        from {{ ref('stg_senado__senadores') }}
        where true
        qualify data_referencia = max(data_referencia) over ()
    ) as s
        on s.id_senador = c.id_senador
),

unidas as (
    select * from camara
    union all
    select * from senado
),

-- CPF e CNPJ seguem a validação; o resto não é documento de fornecedor:
-- CPF_MASCARADO (o Senado publica `240.***.***-04`) e CODIGO_CAMARA (`000000000000NN`, que
-- a Câmara usa para serviços internos, como telefonia e Correios, e fornecedores estrangeiros)
classificadas as (
    select
        *,
        case
            when fornecedor_documento_mascarado is not null then 'CPF_MASCARADO'
            when casa = 'camara' and regexp_matches(fornecedor_documento, '^0{12}[0-9]{2}$')
                then 'CODIGO_CAMARA'
            else {{ tipo_documento('fornecedor_documento') }}
        end as fornecedor_tipo_documento
    from unidas
)

select
    * exclude (fornecedor_documento, fornecedor_documento_mascarado, fornecedor_tipo_documento),
    try(make_date(ano::integer, mes::integer, 1)) as data_competencia,
    coalesce(fornecedor_documento_mascarado, fornecedor_documento) as fornecedor_documento,
    fornecedor_tipo_documento,
    case fornecedor_tipo_documento
        when 'CPF' then {{ documento_valido('fornecedor_documento') }}
        when 'CNPJ' then {{ documento_valido('fornecedor_documento') }}
        when 'INVALIDO' then false
    end as fornecedor_documento_valido,
    if(fornecedor_tipo_documento = 'CNPJ', substr(fornecedor_documento, 1, 8), null)
        as fornecedor_cnpj_raiz
from classificadas
