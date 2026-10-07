"""Adaptador `webdav_zip`: base do CNPJ da Receita, recortada às raízes de interesse.

A Receita publica uma pasta por competência (`AAAA-MM/`) num compartilhamento WebDAV, com ZIPs
de CSV sem cabeçalho em Latin-1. Cada ZIP é baixado (com retomada), lido em fluxo sem extrair e
apagado; só os registros das raízes de interesse vão para o CSV do recorte, em UTF-8 e com
cabeçalho. O recorte é o que se arquiva: os ZIPs (7,6 GB por mês) ficam só com o hash no registro.
"""

from __future__ import annotations

import csv
import fnmatch
import hashlib
import os
import re
import zipfile
from collections.abc import Iterable, Iterator
from datetime import date
from pathlib import Path
from typing import IO, Any

from coletor.adaptadores.base import ErroColeta, Extracao, Preparado
from coletor.competencias import Competencia
from coletor.hashes import sha256_arquivo
from coletor.http import ClienteHttp
from coletor.manifesto import Recurso

PASTA_COMPETENCIA = re.compile(r"^\d{4}-\d{2}$")


def _usuario(recurso: Recurso) -> str:
    usuario = recurso.parametros.get("usuario")
    if not isinstance(usuario, str) or not usuario:
        raise ErroColeta(f"{recurso.id}: parametros.usuario (token do compartilhamento) ausente")
    return usuario


def competencia_disponivel(recurso: Recurso, http: ClienteHttp) -> Competencia:
    """A pasta `AAAA-MM` mais recente do compartilhamento."""
    pastas = [
        item.nome
        for item in http.listar_webdav(recurso.url, _usuario(recurso))
        if item.pasta and PASTA_COMPETENCIA.match(item.nome)
    ]
    if not pastas:
        raise ErroColeta(f"nenhuma pasta AAAA-MM em {recurso.url}: o link mudou?")
    rotulo = max(pastas)
    return Competencia.de_mes(int(rotulo[:4]), int(rotulo[5:]))


def caminho_raizes(relativo: str) -> Path:
    """O Parquet das raízes fica no lago, que o dbt e o coletor acham pela mesma variável."""
    return Path(os.environ.get("ELEITORADO_LAGO", "dados")) / relativo


def carregar_raizes(caminho: Path) -> frozenset[bytes]:
    import duckdb

    if not caminho.exists():
        raise ErroColeta(
            f"{caminho} não existe: o pipeline diário gera (int_rfb__raizes_interesse) e o "
            "estado restaurar traz do bucket"
        )
    linhas = duckdb.sql(f"select raiz from read_parquet('{caminho.as_posix()}')").fetchall()
    raizes = frozenset(raiz.encode("ascii") for (raiz,) in linhas if raiz)
    if not raizes:
        raise ErroColeta(f"{caminho} está vazio: o recorte sairia vazio")
    return raizes


def registros(fluxo: Iterable[bytes]) -> Iterator[bytes]:
    """Registros do CSV em bytes. Um registro termina numa quebra de linha com número par de
    aspas acumuladas: quebra de linha dentro de campo entre aspas continua o registro.
    """
    pendente = b""
    for linha in fluxo:
        pendente += linha
        if pendente.count(b'"') % 2 == 0:
            yield pendente
            pendente = b""
    if pendente:
        yield pendente


def _texto(registro: bytes) -> str:
    # Latin-1 decodifica qualquer byte; a fonte tem NUL soltos, que não são texto
    return registro.decode("latin-1").replace("\x00", "")


def _conferir_colunas(registro: bytes, esperadas: int, nome: str) -> None:
    campos = next(csv.reader([_texto(registro).rstrip("\r\n")], delimiter=";"))
    if len(campos) != esperadas:
        raise ErroColeta(
            f"{nome}: {len(campos)} colunas, o layout tem {esperadas}: a Receita mudou o layout?"
        )


def recortar(
    fluxo: Iterable[bytes],
    saida: IO[bytes],
    raizes: frozenset[bytes] | None,
    colunas: int,
    nome: str,
) -> tuple[int, int]:
    """Copia para `saida` (UTF-8) os registros cujo CNPJ básico está em `raizes` (todos, se
    None). Devolve (lidos, mantidos).
    """
    lidos = mantidos = 0
    for registro in registros(fluxo):
        if lidos == 0:
            _conferir_colunas(registro, colunas, nome)
        lidos += 1
        # o registro começa com aspas: o CNPJ básico ocupa os bytes 1 a 8
        if raizes is None or registro[1:9] in raizes:
            saida.write(_texto(registro).encode("utf-8"))
            mantidos += 1
    return lidos, mantidos


def _membro_unico(compactado: zipfile.ZipFile, nome: str) -> zipfile.ZipInfo:
    membros = [m for m in compactado.infolist() if not m.is_dir()]
    if len(membros) != 1:
        raise ErroColeta(f"{nome}: ZIP com {len(membros)} arquivos, esperado 1")
    return membros[0]


def extrair(
    recurso: Recurso, competencia: Competencia | None, pasta: Path, http: ClienteHttp, hoje: date
) -> Extracao:
    assert recurso.recorte is not None
    recorte = recurso.recorte
    usuario = _usuario(recurso)
    if competencia is None:
        competencia = competencia_disponivel(recurso, http)
    raizes = carregar_raizes(caminho_raizes(recorte.raizes)) if recorte.raizes else None
    url_pasta = f"{recurso.url.rstrip('/')}/{competencia.rotulo}/"
    nomes = sorted(
        item.nome
        for item in http.listar_webdav(url_pasta, usuario)
        if not item.pasta and fnmatch.fnmatchcase(item.nome, recorte.arquivos)
    )
    if not nomes:
        raise ErroColeta(f"nenhum arquivo {recorte.arquivos} em {url_pasta}")
    original = pasta / "recorte.csv"
    arquivos: list[dict[str, Any]] = []
    with original.open("wb") as saida:
        cabecalho = ";".join(f'"{coluna}"' for coluna in recorte.colunas) + "\n"
        saida.write(cabecalho.encode("utf-8"))
        for nome in nomes:
            zip_ = pasta / nome
            download = http.baixar_retomando(f"{url_pasta}{nome}", zip_, usuario)
            with zipfile.ZipFile(zip_) as compactado:
                with compactado.open(_membro_unico(compactado, nome)) as fluxo:
                    lidos, mantidos = recortar(fluxo, saida, raizes, len(recorte.colunas), nome)
            zip_.unlink()  # o disco nunca guarda mais que um ZIP
            arquivos.append(
                {
                    "nome": nome,
                    "bytes": download.bytes,
                    "sha256": download.sha256,
                    "linhas_lidas": lidos,
                    "linhas_mantidas": mantidos,
                }
            )
    resumo = hashlib.sha256("".join(f"{a['nome']} {a['sha256']}\n" for a in arquivos).encode())
    return Extracao(
        competencia=competencia,
        arquivo_original=original,
        extensao="csv",
        url=url_pasta,
        http_status=200,
        bytes_arquivo=sum(a["bytes"] for a in arquivos),
        sha256_arquivo=resumo.hexdigest(),
        parametros={"arquivos": arquivos, "raizes": recorte.raizes},
    )


def preparar(recurso: Recurso, competencia: Competencia, original: Path, pasta: Path) -> Preparado:
    return Preparado(sha256_conteudo=sha256_arquivo(original), csv=original)
