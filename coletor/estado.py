"""Estado entre execuções: o lago local espelha `raw/`, `meta/` e `estado/` do bucket privado.

O arquivo .duckdb do dbt é descartável. O único estado que não se recalcula a partir do raw são
os históricos por eventos, exportados para `estado/historicos/<modelo>.parquet` a cada execução.
Versões sobrescritas ou apagadas ficam 30 dias na exclusão reversível do bucket.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime
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
    consolidados: int = 0


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
    resumo.consolidados = consolidar_particoes(lago)
    carregar_historicos(lago / "estado" / "historicos", banco)
    log.info(
        "estado restaurado: %d arquivo(s) baixado(s), %d partição(ões) consolidada(s)",
        resumo.baixados,
        resumo.consolidados,
    )
    return resumo


def consolidar_particoes(lago: Path) -> int:
    """Deixa em cada partição do raw só o arquivo da carga mais recente; devolve quantas mudaram.

    A carga substitui a partição inteira (`<coleta_id>.parquet`), mas o restaurar só acrescenta:
    se o `estado salvar` falhou depois de uma recoleta, o bucket guarda a coleta antiga e o cache
    a nova, e as duas se juntariam (31/10/2026: sanções em dobro). Vale a carga mais recente do
    meta; partição com arquivo que o meta não conhece fica como está, com um aviso.
    """
    raiz = lago / "raw"
    if not raiz.exists():
        return 0
    repetidas = {
        pasta: arquivos
        for pasta in raiz.glob("*/*/*")
        if pasta.is_dir()
        and not pasta.relative_to(lago).as_posix().startswith(PREFIXOS_TSE)
        and len(arquivos := sorted(pasta.glob("*.parquet"))) > 1
    }
    if not repetidas:
        return 0
    cargas = _cargas_no_meta(lago)
    consolidadas = 0
    for pasta, arquivos in sorted(repetidas.items()):
        desconhecidos = [a.stem for a in arquivos if a.stem not in cargas]
        if desconhecidos:
            log.warning(
                "%s tem %d arquivos e o meta não conhece %s: nada apagado",
                pasta.relative_to(lago).as_posix(),
                len(arquivos),
                ", ".join(desconhecidos),
            )
            continue
        vigente = max(arquivos, key=lambda arquivo: cargas[arquivo.stem])
        for arquivo in arquivos:
            if arquivo != vigente:
                log.warning("%s: substituído por %s", arquivo.relative_to(lago), vigente.name)
                arquivo.unlink()
        consolidadas += 1
    return consolidadas


def _cargas_no_meta(lago: Path) -> dict[str, datetime]:
    """coleta_id → fim da carga, das coletas que gravaram no raw."""
    import duckdb

    arquivos = (lago / "meta" / "coletas").as_posix() + "/*/*.parquet"
    conexao = duckdb.connect()
    try:
        linhas = conexao.execute(
            f"select coleta_id, max(finalizada_em) from read_parquet('{arquivos}', "
            "union_by_name = true) where status in ('carregada', 'recarregada') "
            "and destino = 'raw' group by coleta_id"
        ).fetchall()
    except duckdb.IOException:  # meta vazio
        return {}
    finally:
        conexao.close()
    return dict(linhas)


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
