-- Detalhe dos deputados (nome civil e CPF completo): só no lago privado, para o alerta de
-- parlamentar sócio de fornecedor. Todas as datas de referência coletadas.
select
    _coleta_id,
    _competencia_data as data_referencia,
    json_extract_string(payload, '$.id') as id_deputado,
    json_extract_string(payload, '$.nomeCivil') as nome_civil,
    {{ normalizar_documento("json_extract_string(payload, '$.cpf')") }} as cpf
from {{ source('raw_camara', 'deputados_detalhe') }}
