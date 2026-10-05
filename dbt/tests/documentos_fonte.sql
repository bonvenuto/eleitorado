-- Documento como a fonte publica: CPF já mascarado fica como veio; `-11` é sigilo; `-3`, sem informação.
with casos (entrada, documento, tipo) as (
    values
        ('***.444.712-**', '***.444.712-**', 'CPF_MASCARADO'),
        ('-11', null, 'SIGILOSO'),
        ('-3', null, null),
        ('11.222.333/0001-81', '11222333000181', 'CNPJ'),
        ('111.444.777-35', '11144477735', 'CPF'),
        ('123', '123', 'INVALIDO'),
        (null, null, null)
)

select *
from (
    select
        *,
        {{ documento_fonte('entrada') }} as documento_obtido,
        {{ tipo_documento_fonte('entrada') }} as tipo_obtido,
        {{ nome_normalizado("'  José   da  SILVA '") }} as nome_obtido
    from casos
)
where documento_obtido is distinct from documento
    or tipo_obtido is distinct from tipo
    or nome_obtido != 'JOSE DA SILVA'
