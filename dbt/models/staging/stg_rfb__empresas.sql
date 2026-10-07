-- Empresas (CNPJ básico) do recorte da Receita, em todas as competências coletadas.
select
    _coleta_id,
    _competencia as competencia,
    {{ texto('cnpj_basico') }} as cnpj_raiz,
    {{ texto('razao_social') }} as razao_social,
    {{ texto('natureza_juridica') }} as natureza_juridica_codigo,
    {{ texto('qualificacao_responsavel') }} as qualificacao_responsavel_codigo,
    {{ numero_rfb('capital_social') }} as capital_social,
    {{ texto('porte_empresa') }} as porte_codigo,
    {{ texto('ente_federativo_responsavel') }} as ente_federativo_responsavel
from {{ source('raw_rfb', 'empresas') }}
