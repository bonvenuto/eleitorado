-- CEAP da Câmara: uma linha por linha publicada. Decimal com ponto e datas ISO.
with origem as (
    select * from {{ source('raw_camara', 'ceap') }}
)

select
    _coleta_id,
    _competencia,
    _linha,
    {{ texto('txnomeparlamentar') }} as nome_beneficiario,
    {{ texto('cpf') }} as cpf_parlamentar,
    {{ texto('idecadastro') }} as id_deputado,
    {{ texto('sguf') }} as uf_sigla,
    {{ texto('sgpartido') }} as partido_sigla,
    {{ texto('txtdescricao') }} as categoria,
    {{ texto('txtdescricaoespecificacao') }} as subcategoria,
    {{ texto('txtfornecedor') }} as fornecedor_nome,
    {{ normalizar_documento('txtcnpjcpf') }} as fornecedor_documento,
    {{ texto('txtnumero') }} as numero_documento,
    try_cast(substr({{ texto('datemissao') }}, 1, 10) as date) as data_emissao,
    {{ numero(texto('vlrdocumento')) }} as valor_documento,
    {{ numero(texto('vlrglosa')) }} as valor_glosa,
    {{ numero(texto('vlrliquido')) }} as valor_reembolsado,
    try_cast({{ texto('nummes') }} as bigint) as mes,
    try_cast({{ texto('numano') }} as bigint) as ano,
    {{ texto('txtpassageiro') }} as passageiro,
    {{ texto('txttrecho') }} as trecho,
    {{ texto('idedocumento') }} as id_documento_origem,
    {{ texto('urldocumento') }} as url_documento,
    -- conteúdo publicado da linha, sem as colunas de controle
    md5(to_json(struct_pack(*columns(* exclude (
        _coleta_id, _competencia, _competencia_data, _linha, _arquivo_original, _carregado_em
    ))))) as hash_linha
from origem
