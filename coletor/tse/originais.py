"""Recibos privados dos ZIPs observados, inclusive os estruturalmente rejeitados."""

from pathlib import Path

from coletor.adaptadores.base import ErroColeta, Extracao
from coletor.armazenamento import Armazenamento
from coletor.hashes import sha256_arquivo
from coletor.manifesto import RecursoCompleto
from coletor.tse.durabilidade import gravar_json, ler_json_conferido
from coletor.tse.versoes import id_versao


def arquivar_original(
    lago: Path,
    recurso: RecursoCompleto,
    extracao: Extracao,
    armazenamento: Armazenamento,
    prefixo: str,
) -> str:
    """Chave remota pelo hash; recibo só nasce depois de enviar retornar com sucesso."""
    if sha256_arquivo(extracao.arquivo_original) != extracao.sha256_arquivo:
        raise ErroColeta("hash físico do ZIP divergente antes do arquivo")
    versao_id = id_versao(recurso, extracao)
    caminho = (
        f"{prefixo}originais/tse/{recurso.recurso.id}/"
        f"{extracao.competencia.rotulo}/{extracao.sha256_arquivo}.zip"
    )
    identidade = {
        "versao_id": versao_id,
        "recurso_id": recurso.id,
        "ano": extracao.competencia.data.year,
        "sha256_zip": extracao.sha256_arquivo,
        "bytes_arquivo": extracao.bytes_arquivo,
        "caminho": caminho,
    }
    recibo = lago / "estado/tse/originais" / f"{versao_id}.json"
    if recibo.exists():
        dados = ler_json_conferido(recibo)
        if any(dados.get(c) != v for c, v in identidade.items()):
            raise ErroColeta("colisão no recibo do original TSE")
        return dados["arquivo_original"]
    uri = armazenamento.enviar(extracao.arquivo_original, caminho)
    gravar_json(recibo, {**identidade, "url": extracao.url, "arquivo_original": uri}, checksum=True)
    return uri
