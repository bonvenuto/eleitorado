-- Opção pelo Simples Nacional e pelo MEI das empresas do recorte da Receita.
select
    _coleta_id,
    _competencia as competencia,
    {{ texto('cnpj_basico') }} as cnpj_raiz,
    {{ texto('opcao_pelo_simples') }} = 'S' as optante_simples,
    {{ data_rfb('data_opcao_simples') }} as data_opcao_simples,
    {{ data_rfb('data_exclusao_simples') }} as data_exclusao_simples,
    {{ texto('opcao_mei') }} = 'S' as optante_mei,
    {{ data_rfb('data_opcao_mei') }} as data_opcao_mei,
    {{ data_rfb('data_exclusao_mei') }} as data_exclusao_mei
from {{ source('raw_rfb', 'simples') }}
