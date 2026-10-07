-- Sempre privado. Retido é a soma fisicamente preservada; NÃO significa publicável.
-- Consumidores precisam filtrar fato_elegivel. Grupos divergentes mantêm todas as linhas.
-- Bruto = retido + removido; valores inválidos continuam NULL, sem inventar zero.
select
    cd_eleicao, sq_prestador_contas, sq_despesa, tipo_prestacao, data_prestacao,
    sq_parcelamento_despesa, ano_arquivo, versao_id,
    'tse_pagamentos_identicos_v1'::varchar as politica_versao,
    sum(quantidade_originais)::bigint as linhas_brutas,
    count(*) as linhas_retidas,
    (sum(quantidade_originais) - count(*))::bigint as repeticoes_removidas,
    sum(valor * quantidade_originais)::decimal(38,2) as valor_bruto,
    sum(valor)::decimal(38,2) as valor_retido,
    sum(valor * (quantidade_originais - 1))::decimal(38,2) as valor_removido,
    bool_or(parcela_divergente) as parcela_divergente,
    bool_or(not fato_elegivel) as pendente,
    list(distinct motivo_pendencia) filter (where motivo_pendencia is not null)
        as motivos_pendencia,
    list(struct_pack(item_id := item_id, linha_original := linha_original,
        quantidade_originais := quantidade_originais,
        origens_privadas := origens_parcela_privadas)) as evidencias_privadas
from {{ ref('int_tse__pagamentos') }}
group by cd_eleicao, sq_prestador_contas, sq_despesa, tipo_prestacao, data_prestacao,
    sq_parcelamento_despesa, ano_arquivo, versao_id
