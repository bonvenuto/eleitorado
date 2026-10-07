"""Estado entre execuções: o lago local espelha `raw/`, `meta/` e `estado/` do bucket privado.

O arquivo .duckdb do dbt é descartável. O único estado que não se recalcula a partir do raw são
os históricos por eventos, exportados para `estado/historicos/<modelo>.parquet` a cada execução.
Versões sobrescritas ou apagadas ficam 30 dias na exclusão reversível do bucket.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

from coletor.armazenamento import Armazenamento

log = logging.getLogger(__name__)

HISTORICOS = ("int_cgu__sancoes_eventos", "int_parlamentares__eventos")
SCHEMA_HISTORICOS = "intermediate"
PASTAS = ("raw/", "meta/", "estado/")
PASTAS_ADITIVO = ("raw/", "meta/")  # coleta fora do pipeline: nunca os históricos
ESPELHADAS = ("raw/", "estado/")  # o que sumiu do lago some do bucket; meta/ só cresce
PREFIXOS_TSE = ("raw/tse/", "estado/tse/")
LIMITE_REMOCAO = 0.5  # fração do bucket que uma execução pode apagar


class ErroSincronia(Exception):
    """A sincronização apagaria demais: provável lago local vazio ou incompleto."""


@dataclass
class Resumo:
    baixados: int = 0
    enviados: int = 0
    apagados: int = 0


def md5_arquivo(caminho: Path) -> str:
    resumo = hashlib.md5()  # noqa: S324 - comparação com o MD5 que o GCS informa, não segurança
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1 << 20), b""):
            resumo.update(bloco)
    return resumo.hexdigest()


def _locais(lago: Path, pasta: str) -> dict[str, Path]:
    raiz = lago / pasta
    if not raiz.exists():
        return {}
    return {
        caminho.relative_to(lago).as_posix(): caminho
        for caminho in raiz.rglob("*")
        if caminho.is_file()
    }


def restaurar(armazenamento: Armazenamento, prefixo: str, lago: Path, banco: Path) -> Resumo:
    """Completa o lago com o que falta ou mudou no bucket e recria os históricos no banco."""
    resumo = Resumo()
    for pasta in PASTAS:
        for caminho, objeto in armazenamento.listar_objetos(prefixo + pasta).items():
            relativo = caminho.removeprefix(prefixo)
            if relativo.startswith(PREFIXOS_TSE):
                continue
            local = lago / relativo
            if local.exists() and local.stat().st_size == objeto.tamanho:
                if md5_arquivo(local) == objeto.md5:
                    continue
            local.parent.mkdir(parents=True, exist_ok=True)
            armazenamento.baixar(caminho, local)
            resumo.baixados += 1
    carregar_historicos(lago / "estado" / "historicos", banco)
    log.info("estado restaurado: %d arquivo(s) baixado(s)", resumo.baixados)
    return resumo


def carregar_historicos(pasta: Path, banco: Path) -> list[str]:
    """Cria no banco as tabelas incrementais a partir do Parquet exportado; devolve as criadas."""
    import duckdb

    criadas = []
    banco.parent.mkdir(parents=True, exist_ok=True)
    conexao = duckdb.connect(str(banco))
    try:
        conexao.execute(f"create schema if not exists {SCHEMA_HISTORICOS}")
        for modelo in HISTORICOS:
            arquivo = pasta / f"{modelo}.parquet"
            if not arquivo.exists():
                continue
            conexao.execute(
                f"create or replace table {SCHEMA_HISTORICOS}.{modelo} as "
                f"select * from read_parquet('{arquivo.as_posix()}')"
            )
            criadas.append(modelo)
    finally:
        conexao.close()
    return criadas


def exportar_historicos(banco: Path, pasta: Path) -> list[str]:
    """Grava cada histórico do banco em `<pasta>/<modelo>.parquet`; devolve os exportados."""
    import duckdb

    exportados = []
    pasta.mkdir(parents=True, exist_ok=True)
    conexao = duckdb.connect(str(banco), read_only=True)
    try:
        existentes = {
            nome
            for (nome,) in conexao.execute(
                "select table_name from information_schema.tables where table_schema = ?",
                [SCHEMA_HISTORICOS],
            ).fetchall()
        }
        for modelo in HISTORICOS:
            if modelo not in existentes:
                continue
            destino = pasta / f"{modelo}.parquet"
            conexao.execute(
                f"copy (select * from {SCHEMA_HISTORICOS}.{modelo} order by evento_id) "
                f"to '{destino.as_posix()}' (format parquet, compression zstd)"
            )
            exportados.append(modelo)
    finally:
        conexao.close()
    return exportados


def salvar(
    armazenamento: Armazenamento, prefixo: str, lago: Path, banco: Path, aditivo: bool = False
) -> Resumo:
    """Exporta os históricos e envia ao bucket o que mudou; apaga o que sumiu do lago.

    Primeiro monta o plano inteiro e confere o limite de remoção; só então altera o bucket.

    `aditivo`: para coletas fora do pipeline (a Receita, que bloqueia o GitHub Actions e é coletada
    do computador do mantenedor). O lago local pode estar atrás do bucket, então só envia arquivos
    de `raw/` e `meta/` que o bucket ainda não tem: nada é apagado nem sobrescrito, e os
    históricos não vão.
    """
    if banco.exists() and not aditivo:
        exportar_historicos(banco, lago / "estado" / "historicos")
    envios: list[tuple[Path, str]] = []
    remocoes: list[str] = []
    for pasta in PASTAS_ADITIVO if aditivo else PASTAS:
        remotos = {
            c: o
            for c, o in armazenamento.listar_objetos(prefixo + pasta).items()
            if not c.removeprefix(prefixo).startswith(PREFIXOS_TSE)
        }
        locais = {c: p for c, p in _locais(lago, pasta).items() if not c.startswith(PREFIXOS_TSE)}
        for relativo, local in sorted(locais.items()):
            objeto = remotos.get(prefixo + relativo)
            if objeto is not None and (aditivo or objeto.tamanho == local.stat().st_size):
                if aditivo or objeto.md5 == md5_arquivo(local):
                    continue
            envios.append((local, prefixo + relativo))
        if pasta not in ESPELHADAS or aditivo:
            continue
        sobrando = sorted(set(remotos) - {prefixo + relativo for relativo in locais})
        if remotos and len(sobrando) > max(10, LIMITE_REMOCAO * len(remotos)):
            raise ErroSincronia(
                f"{len(sobrando)} de {len(remotos)} objetos em {prefixo}{pasta} seriam apagados; "
                "confira se o lago local foi restaurado"
            )
        remocoes.extend(sobrando)
    for local, caminho in envios:
        armazenamento.substituir(local, caminho)
    for caminho in remocoes:
        armazenamento.apagar(caminho)
    log.info("estado salvo: %d enviado(s), %d apagado(s)", len(envios), len(remocoes))
    return Resumo(enviados=len(envios), apagados=len(remocoes))
