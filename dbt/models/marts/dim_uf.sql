-- Uma linha por UF, a partir dos municípios do snapshot mais recente do IBGE.
select
    uf_id,
    uf_sigla,
    uf_nome,
    regiao_sigla,
    regiao_nome,
    any_value(_coleta_id) as _coleta_id
from {{ ref('stg_ibge__municipios') }}
group by uf_id, uf_sigla, uf_nome, regiao_sigla, regiao_nome
