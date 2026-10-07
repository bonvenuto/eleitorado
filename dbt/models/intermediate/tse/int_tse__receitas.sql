-- Itens privados da exportação fixada: nenhuma deduplicação por SQ.
-- fato_id agrupa a chave oficial; item_id identifica conteúdo + ocorrência privada.
with identificados as (
    select
        s.*,
        md5(to_json(list_value('receitas', cd_eleicao, sq_prestador_contas,
            sq_receita, tipo_prestacao, cast(data_prestacao as varchar)))) as fato_id,
        {{ tse_linha_id('receitas', [
            'cd_eleicao',
            'sq_prestador_contas',
            'sq_receita',
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
            'cd_fonte_receita',
            'ds_fonte_receita',
            'cd_origem_receita',
            'ds_origem_receita',
            'cd_natureza_receita',
            'ds_natureza_receita',
            'cd_especie_receita',
            'ds_especie_receita',
            'cd_cnae_doador',
            'ds_cnae_doador',
            'nr_cpf_cnpj_doador',
            'nm_doador',
            'nm_doador_rfb',
            'cd_esfera_partidaria_doador',
            'ds_esfera_partidaria_doador',
            'sg_uf_doador',
            'cd_municipio_doador',
            'nm_municipio_doador',
            'sq_candidato_doador',
            'nr_candidato_doador',
            'cd_cargo_candidato_doador',
            'ds_cargo_candidato_doador',
            'nr_partido_doador',
            'sg_partido_doador',
            'nm_partido_doador',
            'nr_recibo_doacao',
            'nr_documento_doacao',
            'sq_receita',
            'dt_receita',
            'ds_receita',
            'vr_receita',
            'ds_natureza_recurso_estimavel',
            'ds_genero',
            'ds_cor_raca',
        ]) }} as item_id
    from {{ ref('stg_tse__receitas') }} s
), ocorrencias as (
    select *, cast(regexp_extract(item_id, '-([0-9]+)$', 1) as bigint) as item_ocorrencia
    from identificados
)
select
    i.*,
    i.vr_receita as valor,
    i.dt_receita as data,
    i.nr_cpf_cnpj_doador as doador_documento,
    i.nr_cpf_cnpj_doador_valido as doador_documento_valido,
    coalesce(c.candidatura_elegivel, false) as candidatura_elegivel,
    coalesce(p.prestacao_ambigua, true) as prestacao_ambigua,
    coalesce(p.origem_ambigua, true) as origem_ambigua,
    coalesce(p.metadados_incompletos, true) as metadados_incompletos,
    coalesce(p.prestacao_elegivel, false) as prestacao_elegivel,
    coalesce(p.prestacao_elegivel, false) and coalesce(c.candidatura_elegivel, false)
        and i.cd_eleicao is not null and i.sq_prestador_contas is not null
        and i.sq_receita is not null and i.sq_candidato is not null as fato_elegivel
from ocorrencias i
left join {{ ref('int_tse__candidaturas') }} c using (candidatura_id)
left join {{ ref('int_tse__prestacoes') }} p
    on p.cd_eleicao = i.cd_eleicao and p.sq_prestador_contas = i.sq_prestador_contas
