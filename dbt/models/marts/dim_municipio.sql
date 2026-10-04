select
    municipio_id,
    municipio_nome,
    uf_sigla,
    microrregiao,
    mesorregiao,
    regiao_imediata,
    regiao_intermediaria,
    _coleta_id
from {{ ref('stg_ibge__municipios') }}
