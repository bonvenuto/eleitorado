"""Gravação privada imutável de uma versão física do ZIP oficial."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
from contextlib import closing
from dataclasses import asdict
from pathlib import Path

from coletor.adaptadores.base import ErroColeta, Extracao
from coletor.conversao import Controle, csv_para_parquet
from coletor.hashes import json_canonico, sha256_arquivo
from coletor.manifesto import RecursoCompleto
from coletor.tse.durabilidade import gravar_json, ler_json_conferido, sincronizar_pasta
from coletor.tse.modelos import FamiliaTse, VersaoTse


def id_versao(recurso: RecursoCompleto, extracao: Extracao) -> str:
    """Identidade física, sem instante de coleta nem caracteres especiais no caminho."""
    return hashlib.sha256(
        json_canonico(
            [recurso.id, extracao.competencia.data.year, extracao.sha256_arquivo]
        ).encode()
    ).hexdigest()


def _semantica(familia: FamiliaTse, pasta: Path, encoding: str) -> tuple[str, list[list[str]]]:
    # Ordenação em disco limita memória; INSERT sem UNIQUE conserva a multiplicidade.
    geracoes = set()
    with closing(sqlite3.connect(pasta / f"{familia.familia}.sqlite")) as banco:
        banco.execute("create table linhas (hash text)")
        with familia.csv.open(encoding=encoding, newline="") as entrada:
            leitor = csv.DictReader(entrada, delimiter=";")
            campos = [c for c in leitor.fieldnames or [] if c not in ("DT_GERACAO", "HH_GERACAO")]
            for linha in leitor:
                geracoes.add((linha.get("DT_GERACAO", ""), linha.get("HH_GERACAO", "")))
                digest = hashlib.sha256(
                    json_canonico([linha[c] for c in campos]).encode()
                ).hexdigest()
                banco.execute("insert into linhas values (?)", (digest,))
        resumo = hashlib.sha256(json_canonico(campos).encode())
        for (digest,) in banco.execute("select hash from linhas order by hash"):
            resumo.update(digest.encode())
    return resumo.hexdigest(), [list(g) for g in sorted(geracoes)]


def gravar_versao(
    lago: Path,
    recurso: RecursoCompleto,
    extracao: Extracao,
    familias: tuple[FamiliaTse, ...],
    controle: Controle,
) -> VersaoTse:
    """Reutiliza somente versão completa e íntegra; colisões jamais sobrescrevem raw."""
    if sha256_arquivo(extracao.arquivo_original) != extracao.sha256_arquivo:
        raise ErroColeta("hash físico do ZIP divergente")
    ano = extracao.competencia.data.year
    if set(f.familia for f in familias) != set(recurso.recurso.familias) or len(familias) != len(
        recurso.recurso.familias
    ):
        raise ErroColeta("famílias incompletas ou duplicadas")
    versao_id = id_versao(recurso, extracao)
    caminhos = {
        f.familia: f"raw/tse/{f.familia}/{ano}/{extracao.sha256_arquivo}/dados.parquet"
        for f in familias
    }
    hashes = {f.familia: sha256_arquivo(f.csv) for f in familias}
    layouts = {f.familia: f.layout_id for f in familias}
    descritor = lago / "estado/tse/versoes" / f"{versao_id}.json"
    with tempfile.TemporaryDirectory(prefix="tse-versao-") as temporario:
        pasta = Path(temporario)
        semanticos = {}
        geracoes = {}
        for familia in familias:
            semanticos[familia.familia], geracoes[familia.familia] = _semantica(
                familia, pasta, recurso.recurso.formato.encoding
            )
        semantico = hashlib.sha256(json_canonico(semanticos).encode()).hexdigest()
        versao = VersaoTse(
            recurso.id,
            ano,
            versao_id,
            extracao.sha256_arquivo,
            caminhos,
            hashes,
            layouts,
            semantico,
        )
        if descritor.exists():
            anterior = json.loads(descritor.read_text(encoding="utf-8"))
            if any(anterior.get(c) != v for c, v in asdict(versao).items()):
                raise ErroColeta("colisão no descritor da versão TSE")
            for familia, caminho in caminhos.items():
                arquivo = lago / caminho
                if (
                    not arquivo.is_file()
                    or sha256_arquivo(arquivo) != anterior["hashes_parquet"][familia]
                ):
                    raise ErroColeta("integridade do raw TSE divergente")
            return versao
        tentativa = lago / "estado/tse/tentativas" / versao_id
        if not tentativa.exists():
            if any((lago / caminho).exists() for caminho in caminhos.values()):
                raise ErroColeta("colisão de caminho raw TSE sem tentativa durável")
            tentativa.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(
                prefix=".preparacao-", dir=tentativa.parent
            ) as preparo:
                duravel = Path(preparo)
                contagens = {}
                hashes_parquet = {}
                for familia in familias:
                    parquet = duravel / f"{familia.familia}.parquet"
                    resultado = csv_para_parquet(
                        familia.csv, parquet, recurso.recurso.formato, controle
                    )
                    # Fecha a cópia antes do fsync e antes de tornar a tentativa instalável.
                    copia = duravel / f"{familia.familia}.copia"
                    with parquet.open("rb") as origem, copia.open("xb") as saida:
                        shutil.copyfileobj(origem, saida)
                        saida.flush()
                        os.fsync(saida.fileno())
                    os.replace(copia, parquet)
                    contagens[familia.familia] = resultado.linhas
                    hashes_parquet[familia.familia] = sha256_arquivo(parquet)
                dados = {
                    **asdict(versao),
                    "url": extracao.url,
                    "arquivo_original": controle.arquivo_original,
                    "coleta_id": controle.coleta_id,
                    "geracoes": geracoes,
                    "contagens": contagens,
                    "hashes_parquet": hashes_parquet,
                    "membros": {f.familia: f.membro for f in familias},
                }
                controles = {
                    "coleta_id": controle.coleta_id,
                    "competencia": controle.competencia,
                    "competencia_data": controle.competencia_data.isoformat(),
                    "arquivo_original": controle.arquivo_original,
                    "carregado_em": controle.carregado_em.isoformat(),
                }
                gravar_json(
                    duravel / "manifesto.json",
                    {"protocolo": "tse:tentativa:v1", "descritor": dados, "controle": controles},
                    checksum=True,
                )
                sincronizar_pasta(duravel)
                if tentativa.exists():
                    raise ErroColeta("colisão de tentativa TSE concorrente")
                os.rename(duravel, tentativa)
                sincronizar_pasta(tentativa.parent)
        manifesto = ler_json_conferido(tentativa / "manifesto.json")
        dados = manifesto["descritor"]
        controles = manifesto["controle"]
        if manifesto["protocolo"] != "tse:tentativa:v1" or any(
            dados.get(c) != v for c, v in asdict(versao).items()
        ):
            raise ErroColeta("colisão no manifesto da tentativa TSE")
        if (
            controles["coleta_id"] != dados["coleta_id"]
            or controles["arquivo_original"] != dados["arquivo_original"]
            or controles["competencia"] != extracao.competencia.rotulo
            or controles["competencia_data"] != extracao.competencia.data.isoformat()
            or controles["arquivo_original"] != controle.arquivo_original
        ):
            raise ErroColeta("controles da tentativa TSE divergentes")
        # Confere todas as fontes e todos os destinos antes de retomar qualquer instalação.
        for familia, caminho in caminhos.items():
            preparado = tentativa / f"{familia}.parquet"
            esperado = dados["hashes_parquet"][familia]
            if not preparado.is_file() or sha256_arquivo(preparado) != esperado:
                raise ErroColeta("integridade da preparação durável TSE divergente")
            destino = lago / caminho
            if destino.exists() and (not destino.is_file() or sha256_arquivo(destino) != esperado):
                raise ErroColeta("colisão de raw com tentativa durável TSE")
        for familia, caminho in caminhos.items():
            destino = lago / caminho
            destino.parent.mkdir(parents=True, exist_ok=True)
            if not destino.exists():
                os.link(tentativa / f"{familia}.parquet", destino)
            sincronizar_pasta(destino.parent)
        gravar_json(descritor, dados)
    return versao
