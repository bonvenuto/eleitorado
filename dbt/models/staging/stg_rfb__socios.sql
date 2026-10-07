-- Sócios das empresas do recorte da Receita, em todas as competências coletadas. O CPF de sócio
-- pessoa física e de representante legal vem mascarado pela Receita (`***456789**`).
select
    _coleta_id,
    _competencia as competencia,
    {{ texto('cnpj_basico') }} as cnpj_raiz,
    {{ texto('identificador_socio') }} as tipo_socio_codigo,
    {{ texto('nome_socio_razao_social') }} as nome_socio,
    {{ texto('cnpj_cpf_socio') }} as documento_socio,
    {{ texto('qualificacao_socio') }} as qualificacao_codigo,
    {{ data_rfb('data_entrada_sociedade') }} as data_entrada,
    {{ texto('pais') }} as pais_codigo,
    {{ texto('representante_legal') }} as representante_documento,
    {{ texto('nome_representante') }} as nome_representante,
    {{ texto('qualificacao_representante_legal') }} as qualificacao_representante_codigo,
    {{ texto('faixa_etaria') }} as faixa_etaria_codigo
from {{ source('raw_rfb', 'socios') }}
