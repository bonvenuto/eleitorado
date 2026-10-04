-- Casos conhecidos das macros de documento (CPF, CNPJ numérico e alfanumérico).
with casos as (
    select * from unnest([
        struct('111.444.777-35' as entrada, 'CPF' as tipo, true as valido),
        struct('11144477734', 'CPF', false),
        struct('00000000000', 'CPF', false),
        struct('11.222.333/0001-81', 'CNPJ', true),
        struct('11222333000180', 'CNPJ', false),
        struct('12.ABC.345/01DE-35', 'CNPJ', true),
        struct('12abc34501de35', 'CNPJ', true),
        struct('1234567890123', 'INVALIDO', false),
        -- pontuação fora do lugar não importa: só os caracteres contam
        struct('071.414.740/0010-0', 'CNPJ', true),
        struct(cast(null as string), cast(null as string), cast(null as bool))
    ])
),

calculados as (
    select
        entrada, tipo, valido,
        {{ normalizar_documento('entrada') }} as documento
    from casos
)

select *
from (
    select
        *,
        {{ tipo_documento('documento') }} as tipo_obtido,
        {{ documento_valido('documento') }} as valido_obtido,
        {{ documento_publico('documento') }} as publico_obtido,
        {{ mascarar_cpfs_em_texto("concat('JOSE DA SILVA ', coalesce(entrada, ''))") }} as texto_obtido
    from calculados
)
where tipo_obtido is distinct from tipo
    or valido_obtido is distinct from valido
    or (tipo = 'CPF' and publico_obtido != concat('***.', substr(documento, 4, 3), '.', substr(documento, 7, 3), '-**'))
    or (tipo = 'CPF' and texto_obtido != concat('JOSE DA SILVA ', publico_obtido))
    or (tipo = 'CNPJ' and texto_obtido != concat('JOSE DA SILVA ', entrada))
