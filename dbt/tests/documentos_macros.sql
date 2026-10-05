-- Casos conhecidos das macros de documento (CPF, CNPJ numérico e alfanumérico).
with casos (entrada, tipo, valido) as (
    values
        ('111.444.777-35', 'CPF', true),
        ('11144477734', 'CPF', false),
        ('00000000000', 'CPF', false),
        ('11.222.333/0001-81', 'CNPJ', true),
        ('11222333000180', 'CNPJ', false),
        ('12.ABC.345/01DE-35', 'CNPJ', true),
        ('12abc34501de35', 'CNPJ', true),
        ('1234567890123', 'INVALIDO', false),
        ('123456789', 'INVALIDO', false),
        -- pontuação fora do lugar não importa: só os caracteres contam
        ('071.414.740/0010-0', 'CNPJ', true),
        (null, null, null)
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
    -- CPF que perdeu zeros à esquerda (9 ou 10 dígitos) também sai mascarado
    or (entrada = '123456789' and publico_obtido != '***.234.567-**')
