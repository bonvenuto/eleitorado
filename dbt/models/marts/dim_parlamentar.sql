-- Câmara e Senado num só cadastro (`camara:<id>`, `senado:<CodigoParlamentar>`).
-- O CPF do deputado não entra nos marts (seção 7.6 da spec).
select
    parlamentar_id,
    casa,
    id_origem,
    nome,
    uf_sigla,
    partido_sigla,
    legislaturas,
    url_foto,
    _coleta_id
from {{ ref('int_parlamentares__snapshots') }}
where true
qualify data_referencia = max(data_referencia) over (partition by casa)
