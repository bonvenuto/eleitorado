-- Itens privados da exportação fixada: nenhuma deduplicação por SQ.
-- fato_id agrupa a chave oficial; item_id identifica conteúdo + ocorrência privada.
with identificados as (
    select
        s.*,
        md5(to_json(list_value('contratadas', cd_eleicao, sq_prestador_contas,
            sq_despesa, tipo_prestacao, cast(data_prestacao as varchar)))) as fato_id,
        {{ tse_linha_id('contratadas', [
            'cd_eleicao',
            'sq_prestador_contas',
            'sq_despesa',
            'tipo_prestacao',
            'data_prestacao',
        ], [
            'aa_eleicao',
            'cd_tipo_eleicao',
            'nm_tipo_eleicao',
            'cd_eleicao',
            'ds_eleicao',
            'dt_eleicao',
            'st_turno',
            'tp_prestacao_contas',
            'dt_prestacao_contas',
            'sq_prestador_contas',
            'sg_uf',
            'sg_ue',
            'nm_ue',
            'nr_cnpj_prestador_conta',
            'cd_cargo',
            'ds_cargo',
            'sq_candidato',
            'nr_candidato',
            'nm_candidato',
            'nr_cpf_candidato',
            'nr_cpf_vice_candidato',
            'nr_partido',
            'sg_partido',
            'nm_partido',
            'cd_tipo_fornecedor',
            'ds_tipo_fornecedor',
            'cd_cnae_fornecedor',
            'ds_cnae_fornecedor',
            'nr_cpf_cnpj_fornecedor',
            'nm_fornecedor',
            'nm_fornecedor_rfb',
            'cd_esfera_part_fornecedor',
            'ds_esfera_part_fornecedor',
            'sg_uf_fornecedor',
            'cd_municipio_fornecedor',
            'nm_municipio_fornecedor',
            'sq_candidato_fornecedor',
            'nr_candidato_fornecedor',
            'cd_cargo_fornecedor',
            'ds_cargo_fornecedor',
            'nr_partido_fornecedor',
            'sg_partido_fornecedor',
            'nm_partido_fornecedor',
            'ds_tipo_documento',
            'nr_documento',
            'cd_origem_despesa',
            'ds_origem_despesa',
            'sq_despesa',
            'dt_despesa',
            'ds_despesa',
            'vr_despesa_contratada',
        ]) }} as item_id
    from {{ ref('stg_tse__contratadas') }} s
), ocorrencias as (
    select *, cast(regexp_extract(item_id, '-([0-9]+)$', 1) as bigint) as item_ocorrencia
    from identificados
), elegibilidade as (
    select
        i.*,
        i.vr_despesa_contratada as valor,
        i.dt_despesa as data,
        i.nr_cpf_cnpj_fornecedor as fornecedor_documento,
        i.nr_cpf_cnpj_fornecedor_valido as fornecedor_documento_valido,
        coalesce(c.candidatura_elegivel, false) as candidatura_elegivel,
        coalesce(p.prestacao_ambigua, true) as prestacao_ambigua,
        coalesce(p.origem_ambigua, true) as origem_ambigua,
        coalesce(p.metadados_incompletos, true) as metadados_incompletos,
        coalesce(p.prestacao_elegivel, false) as prestacao_elegivel,
        coalesce(p.prestacao_elegivel, false) and coalesce(c.candidatura_elegivel, false)
            and i.cd_eleicao is not null and i.sq_prestador_contas is not null
            and i.sq_despesa is not null and i.sq_candidato is not null as fato_elegivel
    from ocorrencias i
    left join {{ ref('int_tse__candidaturas') }} c using (candidatura_id)
    left join {{ ref('int_tse__prestacoes') }} p
        on p.cd_eleicao = i.cd_eleicao and p.sq_prestador_contas = i.sq_prestador_contas
)
select
    *,
    count(distinct struct_pack(candidatura := candidatura_id, fornecedor := fornecedor_documento,
        valido := fornecedor_documento_valido)) over (
        partition by cd_eleicao, sq_prestador_contas, sq_despesa, tipo_prestacao, data_prestacao
    ) <> 1 as conflito_mapa_contratada,
    fato_elegivel and fornecedor_documento is not null
        and coalesce(fornecedor_documento_valido, false)
        and not conflito_mapa_contratada as mapa_contratada_elegivel
from elegibilidade
