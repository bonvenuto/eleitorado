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
        # Falhar antes de converter, inclusive se uma interrupção deixou raw sem descritor.
        if any((lago / caminho).exists() for caminho in caminhos.values()):
            raise ErroColeta("colisão de caminho raw TSE sem descritor íntegro")
        contagens = {}
        hashes_parquet = {}
        for familia in familias:
            parquet = pasta / f"{familia.familia}.parquet"
            resultado = csv_para_parquet(familia.csv, parquet, recurso.recurso.formato, controle)
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
        criados = []
        try:
            for familia, caminho in caminhos.items():
                destino = lago / caminho
                destino.parent.mkdir(parents=True, exist_ok=True)
                with destino.open("xb") as saida:
                    criados.append(destino)
                    with (pasta / f"{familia}.parquet").open("rb") as origem:
                        shutil.copyfileobj(origem, saida)
            descritor.parent.mkdir(parents=True, exist_ok=True)
            # O nome definitivo só aparece após todo o JSON estar pronto e sincronizado.
            with tempfile.NamedTemporaryFile(dir=descritor.parent, delete=False) as saida:
                temporario_descritor = Path(saida.name)
                saida.write(json_canonico(dados).encode("utf-8"))
                saida.flush()
                os.fsync(saida.fileno())
            try:
                os.link(temporario_descritor, descritor)
                criados.append(descritor)
            finally:
                temporario_descritor.unlink(missing_ok=True)
        except Exception:
            for criado in reversed(criados):
                criado.unlink(missing_ok=True)
            raise
    return versao
