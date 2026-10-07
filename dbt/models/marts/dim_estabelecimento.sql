-- Estabelecimentos (matriz e filiais) das empresas que aparecem nos dados do eleitorado, um por
-- CNPJ completo. Sem endereço nem contato; CPF dentro do nome fantasia mascarado.
select
    cnpj,
    cnpj_raiz,
    matriz,
    {{ mascarar_cpfs_em_texto('nome_fantasia') }} as nome_fantasia,
    situacao,
    data_situacao,
    motivo as motivo_situacao,
    data_inicio_atividade,
    cnae_principal,
    cnae_principal_descricao,
    municipio_id,
    uf_sigla,
    competencia_receita
from {{ ref('int_rfb__estabelecimentos') }}
