"""Sincronia privada TSE: objetos imutáveis e seletor restaurado após validação."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path

from coletor.armazenamento import Armazenamento
from coletor.estado import PREFIXOS_TSE, Resumo, md5_arquivo
from coletor.hashes import json_canonico, sha256_arquivo
from coletor.tse.durabilidade import ler_json_conferido, sincronizar_pasta
from coletor.tse.modelos import SelecaoTse
from coletor.tse.selecao import (
    COBERTURA,
    CONTRATO,
    criar_selecao,
    digest_entradas,
    digest_selecao,
    rejeicoes_conhecidas,
    validar_selecao,
)
from coletor.tse.validacoes import rejeicoes_pendentes

VIGENTE = "estado/tse/vigente.json"
MARCADOR = "estado/tse/inicializado.json"


def _caminho(lago: Path, relativo: str) -> Path:
    if (
        not relativo.startswith(PREFIXOS_TSE)
        or "\\" in relativo
        or ":" in relativo
        or any(p in ("", ".", "..") for p in relativo.split("/"))
    ):
        raise ValueError("caminho TSE não canônico")
    caminho = lago / relativo
    if not caminho.resolve().is_relative_to(lago.resolve()):
        raise ValueError("caminho TSE fora do lago")
    return caminho


def _duravel(relativo: str) -> bool:
    partes = relativo.split("/")
    return not any(p.startswith(".") for p in partes) and relativo.endswith((".json", ".parquet"))


def _locais(lago: Path) -> dict[str, Path]:
    return {
        p.relative_to(lago).as_posix(): p
        for prefixo in PREFIXOS_TSE
        for p in (lago / prefixo).rglob("*")
        if p.is_file() and _duravel(p.relative_to(lago).as_posix())
    }


def _selecao(caminho: Path) -> SelecaoTse:
    dados = json.loads(caminho.read_bytes())
    if not isinstance(dados, dict) or set(dados) != {"selecao_id", "versoes"}:
        raise ValueError("seleção persistida inválida")
    versoes = dados["versoes"]
    if (
        not isinstance(versoes, dict)
        or set(versoes) != COBERTURA
        or not all(
            isinstance(v, str) and re.fullmatch(r"[0-9a-f]{64}", v) for v in versoes.values()
        )
        or dados["selecao_id"] != criar_selecao(versoes).selecao_id
    ):
        raise ValueError("identidade/cobertura da seleção persistida divergente")
    return SelecaoTse(**dados)


def _validar(lago: Path) -> None:
    # Envelopes e avaliações duráveis são necessários mesmo quando ainda não há vigente.
    for caminho in (lago / "estado/tse/originais").glob("*.json"):
        ler_json_conferido(caminho)
    for pasta in (lago / "estado/tse/tentativas").glob("*"):
        if not pasta.is_dir() or pasta.name.startswith("."):
            continue
        caminho = pasta / "manifesto.json"
        if not caminho.is_file():
            raise ValueError("tentativa durável sem manifesto")
        dados = ler_json_conferido(caminho)
        if dados.get("protocolo") != "tse:tentativa:v1":
            raise ValueError("protocolo de tentativa inválido")
        descritor = dados["descritor"]
        if descritor["versao_id"] != caminho.parent.name:
            raise ValueError("identidade de tentativa divergente")
        for familia, esperado in descritor["hashes_parquet"].items():
            if not re.fullmatch(r"[a-z_]+", familia):
                raise ValueError("família de tentativa inválida")
            if sha256_arquivo(caminho.parent / f"{familia}.parquet") != esperado:
                raise ValueError("hash da tentativa divergente")
    for caminho in (lago / "estado/tse/versoes").glob("*.json"):
        descritor = json.loads(caminho.read_bytes())
        if descritor.get("versao_id") != caminho.stem:
            raise ValueError("identidade do descritor divergente")
        for familia, relativo in descritor["familias"].items():
            if not relativo.startswith("raw/tse/"):
                raise ValueError("raw de versão fora do namespace TSE")
            if sha256_arquivo(_caminho(lago, relativo)) != descritor["hashes_parquet"][familia]:
                raise ValueError("hash de versão privada divergente")
    por_id = {}
    for caminho in (lago / "estado/tse/validacoes").glob("*.json"):
        if sha256_arquivo(caminho) != caminho.stem:
            raise ValueError("hash de avaliação divergente")
        por_id[caminho.stem] = json.loads(caminho.read_bytes())
    avaliacoes = list(por_id.values())
    for avaliacao in avaliacoes:
        for referencia in avaliacao.get("superadas", []):
            anterior = por_id.get(referencia)
            if (
                anterior is None
                or anterior.get("resultado") != "rejeitada"
                or any(
                    anterior.get(c) != avaliacao.get(c)
                    for c in ("escopo", "identidade", "entradas_digest", "contrato")
                )
            ):
                raise ValueError("referência de avaliação ausente ou divergente")
    vigente, marcador = lago / VIGENTE, lago / MARCADOR
    if not vigente.exists() and not marcador.exists():
        return
    if not vigente.is_file() or not marcador.is_file():
        raise ValueError("inicialização TSE sem marcador/seletor íntegros")
    selecao = _selecao(vigente)
    impedimentos = validar_selecao(lago, selecao)
    if impedimentos:
        raise ValueError("; ".join(impedimentos))
    imutavel = lago / f"estado/tse/selecoes/{selecao.selecao_id}.json"
    if not imutavel.is_file() or asdict(_selecao(imutavel)) != asdict(selecao):
        raise ValueError("seleção imutável ausente ou divergente")
    dados_marcador = json.loads(marcador.read_bytes())
    primeira = dados_marcador.get("primeira_selecao_id")
    if (
        dados_marcador.get("protocolo") != "tse:inicializado:v1"
        or not isinstance(primeira, str)
        or not re.fullmatch(r"[0-9a-f]{64}", primeira)
    ):
        raise ValueError("marcador de inicialização inválido")
    primeira_path = lago / f"estado/tse/selecoes/{primeira}.json"
    if not primeira_path.is_file() or _selecao(primeira_path).selecao_id != primeira:
        raise ValueError("primeira seleção do marcador ausente ou divergente")
    entradas = digest_entradas(lago, selecao)
    chave = {
        "escopo": "selecao",
        "identidade": selecao.selecao_id,
        "entradas_digest": entradas,
        "contrato": CONTRATO,
    }
    conhecidas = rejeicoes_conhecidas(lago, selecao, entradas)
    aprovada = False
    for avaliacao in avaliacoes:
        if (
            not all(avaliacao.get(k) == v for k, v in chave.items())
            or avaliacao.get("resultado") != "aprovada"
        ):
            continue
        execucao = avaliacao.get("execucao_id")
        if not isinstance(execucao, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", execucao
        ):
            raise ValueError("execução de aprovação inválida")
        caminho_recibo = lago / f"estado/tse/publicacoes/preparadas/{execucao}/recibo.json"
        if not caminho_recibo.is_file():
            continue
        dados = json.loads(caminho_recibo.read_bytes())
        evidencia = hashlib.sha256(
            json_canonico({k: v for k, v in dados.items() if k != "evidencia"}).encode("utf-8")
        ).hexdigest()
        recibo = dados.get("recibo", {})
        if (
            dados.get("protocolo") == "tse:recibo:v1"
            and dados.get("evidencia") == evidencia == avaliacao.get("evidencia")
            and recibo.get("execucao_id") == execucao
            and recibo.get("entradas_digest") == entradas
            and recibo.get("selecao_digest") == digest_selecao(selecao)
            and recibo.get("resultado") == {"status": "sucesso", "testes_com_erro": 0}
            and dados.get("rejeicoes_conhecidas") == conhecidas
            and sorted(dados.get("superadas", [])) == conhecidas
            and sorted(avaliacao.get("superadas", [])) == conhecidas
        ):
            aprovada = True
    if not aprovada:
        raise ValueError("seleção sem aprovação vinculada a recibo íntegro e atual")
    if rejeicoes_pendentes(lago, **chave):
        raise ValueError("seleção possui rejeição pendente")


def salvar_tse(armazenamento: Armazenamento, prefixo: str, lago: Path) -> Resumo:
    """Envia dependências sem sobrescrever/apagar; vigente é o único objeto mutável."""
    locais = _locais(lago)
    _validar(lago)
    remotos = {
        c: o for p in PREFIXOS_TSE for c, o in armazenamento.listar_objetos(prefixo + p).items()
    }
    envios = []
    for relativo, local in sorted(locais.items()):
        _caminho(lago, relativo)
        remoto = remotos.get(prefixo + relativo)
        if remoto is not None:
            igual = remoto.tamanho == local.stat().st_size and remoto.md5 == md5_arquivo(local)
            if igual:
                continue
            if relativo != VIGENTE:
                raise ValueError(f"colisão de objeto TSE imutável: {relativo}")
        envios.append((relativo, local))
    # O bucket pode conter rejeições mais recentes que este lago. Confere a união
    # antes de qualquer envio, sem adotar seu seletor como candidato local.
    with tempfile.TemporaryDirectory(prefix="tse-envio-") as temporario:
        preparo = Path(temporario)
        for caminho, objeto in sorted(remotos.items()):
            relativo = caminho.removeprefix(prefixo)
            destino = _caminho(preparo, relativo)
            if relativo in (VIGENTE, MARCADOR) or not _duravel(relativo):
                continue
            destino.parent.mkdir(parents=True, exist_ok=True)
            armazenamento.baixar(caminho, destino)
            if destino.stat().st_size != objeto.tamanho or md5_arquivo(destino) != objeto.md5:
                raise ValueError("download TSE com integridade divergente")
        for relativo, local in locais.items():
            destino = _caminho(preparo, relativo)
            if destino.exists() and sha256_arquivo(destino) != sha256_arquivo(local):
                raise ValueError(f"colisão de objeto TSE imutável: {relativo}")
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(local, destino)
        _validar(preparo)
    # Nunca um lago incompleto elimina o marcador ou troca o seletor por preparação.
    if prefixo + MARCADOR in remotos and VIGENTE in locais and MARCADOR not in locais:
        raise ValueError("marcador remoto não pode ser omitido")
    envios.sort(key=lambda item: (item[0] in (VIGENTE, MARCADOR), item[0] == MARCADOR, item[0]))
    for relativo, local in envios:
        if relativo == VIGENTE:
            armazenamento.substituir(local, prefixo + relativo)
        else:
            armazenamento.enviar(local, prefixo + relativo)
    return Resumo(enviados=len(envios))


def restaurar_tse(armazenamento: Armazenamento, prefixo: str, lago: Path) -> Resumo:
    """Baixa e valida em isolamento; só então instala imutáveis, marcador e seletor."""
    remotos = {
        c: o for p in PREFIXOS_TSE for c, o in armazenamento.listar_objetos(prefixo + p).items()
    }
    # Mesmo filesystem permite instalação atômica por arquivo, inclusive no Windows.
    lago.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tse-restauro-", dir=lago.parent) as temporario:
        preparo = Path(temporario)
        baixados = {}
        for caminho, objeto in sorted(remotos.items()):
            relativo = caminho.removeprefix(prefixo)
            destino = _caminho(preparo, relativo)
            if not _duravel(relativo):
                continue
            destino.parent.mkdir(parents=True, exist_ok=True)
            armazenamento.baixar(caminho, destino)
            if destino.stat().st_size != objeto.tamanho or md5_arquivo(destino) != objeto.md5:
                raise ValueError("download TSE com integridade divergente")
            baixados[relativo] = destino
        _validar(preparo)
        # Rejeições locais ainda não enviadas não podem desaparecer sob backup antigo.
        # A união é isolada: não altera nenhum inode/raw/hardlink do lago anterior.
        for relativo, local in _locais(lago).items():
            if relativo in (VIGENTE, MARCADOR):
                continue
            destino = _caminho(preparo, relativo)
            if destino.exists():
                if sha256_arquivo(destino) != sha256_arquivo(local):
                    raise ValueError(f"colisão de objeto TSE local imutável: {relativo}")
            else:
                destino.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(local, destino)
        _validar(preparo)
        instalar = []
        for relativo, origem in baixados.items():
            destino = _caminho(lago, relativo)
            if destino.exists():
                if sha256_arquivo(destino) == sha256_arquivo(origem):
                    continue
                if relativo != VIGENTE:
                    raise ValueError(f"colisão de objeto TSE local imutável: {relativo}")
            instalar.append((relativo, origem, destino))
        # Validações/downloads não escreveram no estado anterior. Nenhum raw é editado em lugar.
        instalar.sort(
            key=lambda item: (item[0] in (VIGENTE, MARCADOR), item[0] == VIGENTE, item[0])
        )
        for _, origem, destino in instalar:
            destino.parent.mkdir(parents=True, exist_ok=True)
            with origem.open("rb+") as entrada:
                os.fsync(entrada.fileno())
            os.replace(origem, destino)
            sincronizar_pasta(destino.parent)
        return Resumo(baixados=len(baixados))
