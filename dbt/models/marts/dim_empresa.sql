-- Cadastro na Receita das empresas que aparecem nos dados do eleitorado (uma linha por raiz do
-- CNPJ). Sem endereço, contato nem sócios; CPF dentro da razão social (MEI) mascarado.
select
    cnpj_raiz,
    {{ mascarar_cpfs_em_texto('razao_social') }} as razao_social,
    natureza_juridica_codigo,
    natureza_juridica,
    porte,
    capital_social,
    data_abertura,
    matriz_cnpj,
    situacao,
    data_situacao,
    motivo as motivo_situacao,
    cnae_principal,
    cnae_principal_descricao,
    municipio_id,
    uf_sigla,
    optante_simples,
    data_opcao_simples,
    data_exclusao_simples,
    optante_mei,
    data_opcao_mei,
    data_exclusao_mei,
    estabelecimentos,
    socios,
    competencia_receita
from {{ ref('int_rfb__empresas') }}
