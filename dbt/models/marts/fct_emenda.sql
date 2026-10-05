-- Emendas parlamentares (snapshot mais recente): uma linha por linha publicada.
select
    md5(concat(hash_linha, '-', cast(row_number() over (partition by hash_linha order by emenda_codigo) as varchar)))
        as emenda_linha_id,
    emenda_codigo,
    ano,
    tipo_emenda,
    autor_codigo,
    {{ mascarar_cpfs_em_texto('autor_nome') }} as autor_nome,
    numero_emenda,
    localidade,
    municipio_id,
    municipio_nome,
    uf_id,
    regiao,
    funcao_codigo, funcao, subfuncao_codigo, subfuncao, programa_codigo, programa, acao_codigo, acao,
    valor_empenhado, valor_liquidado, valor_pago,
    valor_restos_a_pagar_inscritos, valor_restos_a_pagar_cancelados, valor_restos_a_pagar_pagos,
    data_referencia,
    _coleta_id
from {{ ref('stg_cgu__emendas') }}
