-- Participante vencedor de licitação federal que tinha sanção vigente na data da licitação
-- (abertura, ou resultado quando não há abertura). Indício para investigar.
with vencedores as (
    select
        *,
        {{ chave_correspondencia('participante_tipo_documento', 'participante_documento') }} as chave
    from {{ ref('int_cgu__licitacao_participantes') }}
    where vencedor and participante_documento_valido and data_licitacao is not null
),

sancoes as (
    {{ sancoes_para_alerta() }}
),

cruzadas as (
    select
        v.participante_linha_id,
        v.licitacao_id,
        s.sancao_id,
        {{ tipo_correspondencia('v.participante_tipo_documento', 'v.participante_documento', 's.documento') }}
            as tipo_correspondencia,
        v.licitacao_numero,
        v.orgao_nome,
        v.item_descricao,
        v.data_licitacao,
        {{ mascarar_cpfs_em_texto('v.participante_nome') }} as participante_nome,
        {{ documento_publico('v.participante_documento') }} as participante_documento,
        s.cadastro,
        s.categoria as categoria_sancao,
        s.abrangencia,
        s.orgao_sancionador,
        s.data_inicio as sancao_data_inicio,
        s.data_fim as sancao_data_fim,
        v._coleta_id as participante_coleta_id,
        s._coleta_id as sancao_coleta_id,
        s.data_evento as sancao_data_evento
    from vencedores as v
    join sancoes as s
        on s.chave = v.chave
        and v.data_licitacao between s.data_inicio and coalesce(s.data_fim, date '9999-12-31')
)

select
    md5(concat('licitacao_vencedor_sancionado|', participante_linha_id, '|', sancao_id)) as alerta_id,
    * exclude (sancao_data_evento),
    'Vencedor de licitação federal com sanção vigente no CEIS/CNEP na data da licitação '
    || '(correspondência por CPF, CNPJ ou raiz do CNPJ)' as regra
from cruzadas
qualify row_number() over (
    partition by participante_linha_id, sancao_id
    order by if(tipo_correspondencia = 'cnpj_raiz', 1, 0), sancao_data_evento desc
) = 1
