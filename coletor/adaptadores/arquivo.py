"""Adaptador `arquivo`: download HTTP de CSV, com ou sem ZIP."""

from __future__ import annotations

import shutil
import zipfile
from datetime import date
from pathlib import Path

from coletor.adaptadores.base import ErroColeta, Extracao, Preparado, extensao_de, preencher
from coletor.cgu import datas_candidatas, descobrir_data
from coletor.competencias import Competencia
from coletor.hashes import sha256_arquivo
from coletor.http import ClienteHttp, ErroHttp
from coletor.manifesto import Recurso


def extrair(
    recurso: Recurso, competencia: Competencia | None, pasta: Path, http: ClienteHttp, hoje: date
) -> Extracao:
    if recurso.competencia.tipo == "data_arquivo":
        return _extrair_data_arquivo(recurso, pasta, http, hoje)
    if competencia is None:
        raise ErroColeta(f"{recurso.id}: competência obrigatória")
    return _baixar(recurso, competencia, pasta, http, hoje)


def _extrair_data_arquivo(recurso: Recurso, pasta: Path, http: ClienteHttp, hoje: date) -> Extracao:
    assert recurso.competencia.pagina is not None
    try:
        descoberta = descobrir_data(http.obter_texto(recurso.competencia.pagina))
    except ErroHttp:
        descoberta = None
    tentativas: list[str] = []
    for dia in datas_candidatas(descoberta, hoje):
        try:
            return _baixar(recurso, Competencia.de_dia(dia), pasta, http, hoje)
        except ErroHttp as erro:
            if erro.status not in (403, 404):
                raise
            tentativas.append(f"{dia.isoformat()}={erro.status}")
    raise ErroColeta(f"nenhum arquivo disponível ({', '.join(tentativas)})")


def _baixar(
    recurso: Recurso, competencia: Competencia, pasta: Path, http: ClienteHttp, hoje: date
) -> Extracao:
    url = preencher(recurso.url, competencia, hoje)
    temporario = pasta / "download"
    download = http.baixar(url, temporario)
    extensao = extensao_de(download.url_final)
    original = pasta / f"original.{extensao}"
    temporario.replace(original)
    return Extracao(
        competencia=competencia,
        arquivo_original=original,
        extensao=extensao,
        url=download.url_final,
        http_status=download.status,
        bytes_arquivo=download.bytes,
        sha256_arquivo=download.sha256,
        last_modified=download.last_modified,
        etag=download.etag,
    )


def preparar(recurso: Recurso, competencia: Competencia, original: Path, pasta: Path) -> Preparado:
    formato = recurso.formato
    if formato.compressao != "zip":
        return Preparado(sha256_conteudo=sha256_arquivo(original), csv=original)
    destino = pasta / "conteudo.csv"
    with zipfile.ZipFile(original) as compactado:
        membros = [membro for membro in compactado.infolist() if not membro.is_dir()]
        if formato.arquivo:
            nome = preencher(formato.arquivo, competencia, competencia.data)
            escolhido = next((m for m in membros if m.filename == nome), None)
            if escolhido is None:
                nomes = [m.filename for m in membros]
                raise ErroColeta(f"{nome} não está no ZIP (membros: {nomes})")
        elif len(membros) == 1:
            escolhido = membros[0]
        else:
            raise ErroColeta(f"ZIP com {len(membros)} arquivos: defina formato.arquivo")
        with compactado.open(escolhido) as origem, destino.open("wb") as saida:
            shutil.copyfileobj(origem, saida, 1 << 20)
    return Preparado(sha256_conteudo=sha256_arquivo(destino), csv=destino)
