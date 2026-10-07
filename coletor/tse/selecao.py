"""Seleção privada completa e promoção local após evidência dbt vinculada."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlparse

import pyarrow as pa
import pyarrow.parquet as pq

from coletor.conversao import CAMPOS_CONTROLE
from coletor.dbt import ResultadoDbt
from coletor.hashes import json_canonico, sha256_arquivo
from coletor.nomes import normalizar_cabecalho
from coletor.tse.durabilidade import (
    ErroRecuperacaoTse,
    conferir_recuperacao,
    gravar_json,
    instalar_com_compensacao,
    pasta_temporaria,
)
from coletor.tse.evidencias import (
    PROTOCOLO_PREPARACAO,
    conferir_execucao,
    inventario_saida,
)
from coletor.tse.layouts import LAYOUTS, PREFIXOS
from coletor.tse.modelos import ReciboValidacaoTse, SelecaoTse
from coletor.tse.validacoes import gravar_avaliacao, rejeicoes_pendentes

CONTRATO = "tse:selecao:v1"
ANOS = (2018, 2020, 2022, 2024)
FAMILIAS = {
    "tse.candidaturas": ("candidaturas",),
    "tse.bens": ("bens",),
    "tse.contas": ("receitas", "contratadas", "pagamentos", "doador_originario"),
}
COBERTURA = {f"{recurso}:{ano}" for recurso in FAMILIAS for ano in ANOS}


def _digest(dados) -> str:
    return hashlib.sha256(json_canonico(dados).encode("utf-8")).hexdigest()


def _hash(valor) -> bool:
    return isinstance(valor, str) and re.fullmatch(r"[0-9a-f]{64}", valor) is not None


def criar_selecao(versoes: dict[str, str]) -> SelecaoTse:
    """Identidade determinística do vetor exato, sem geração ou relógio adicionais."""
    return SelecaoTse(_digest(versoes), dict(versoes))


def digest_selecao(selecao: SelecaoTse) -> str:
    return _digest(asdict(selecao))


def _confinado(lago: Path, relativo: str) -> Path:
    if not isinstance(relativo, str) or Path(relativo).is_absolute() or "\\" in relativo:
        raise ValueError("caminho privado deve ser relativo e canônico")
    if any(p in ("", ".", "..") for p in relativo.split("/")) or ":" in relativo:
        raise ValueError("caminho privado não canônico")
    caminho = lago / relativo
    if not caminho.resolve().is_relative_to(lago.resolve()):
        raise ValueError("caminho privado fora do lago")
    return caminho


def _descritor(lago: Path, versao_id: str) -> tuple[Path, dict]:
    if not _hash(versao_id):
        raise ValueError("identidade de versão inválida")
    caminho = _confinado(lago, f"estado/tse/versoes/{versao_id}.json")
    if not caminho.is_file():
        raise ValueError("descritor concluído ausente")
    dados = json.loads(caminho.read_bytes())
    if not isinstance(dados, dict):
        raise ValueError("descritor deve ser objeto")
    return caminho, dados


def digest_entradas(lago: Path, selecao: SelecaoTse) -> str:
    """Inclui bytes dos descritores e dos raw exatos; nunca soma versões anteriores."""
    entradas = {}
    for chave, versao_id in sorted(selecao.versoes.items()):
        caminho, dados = _descritor(lago, versao_id)
        arquivos = {}
        for familia, relativo in sorted(dados["familias"].items()):
            raw = _confinado(lago, relativo)
            arquivos[familia] = {"caminho": relativo, "sha256": sha256_arquivo(raw)}
        entradas[chave] = {"descritor": sha256_arquivo(caminho), "arquivos": arquivos}
    return _digest({"selecao": asdict(selecao), "entradas": entradas})


def _validar_versao(lago: Path, chave: str, versao_id: str) -> None:
    _, dados = _descritor(lago, versao_id)
    recurso, ano_texto = chave.split(":")
    ano = int(ano_texto)
    familias = set(FAMILIAS[recurso])
    if (
        dados.get("recurso_id") != recurso
        or type(dados.get("ano")) is not int
        or dados["ano"] != ano
    ):
        raise ValueError("recurso/ano do descritor divergentes")
    if dados.get("versao_id") != versao_id or not _hash(dados.get("sha256_zip")):
        raise ValueError("identidade física inválida")
    if _digest([recurso, ano, dados["sha256_zip"]]) != versao_id:
        raise ValueError("identidade física divergente")
    if not _hash(dados.get("sha256_semantico")):
        raise ValueError("hash semântico inválido")
    for campo in (
        "familias",
        "hashes",
        "hashes_parquet",
        "layouts",
        "contagens",
        "geracoes",
        "membros",
    ):
        if not isinstance(dados.get(campo), dict) or set(dados[campo]) != familias:
            raise ValueError(f"famílias divergentes em {campo}")
    url = urlparse(dados.get("url", ""))
    if (
        url.scheme != "https"
        or not url.hostname
        or not (url.hostname == "tse.jus.br" or url.hostname.endswith(".tse.jus.br"))
        or url.username
        or url.password
    ):
        raise ValueError("URL de origem TSE inválida")
    if not isinstance(dados.get("arquivo_original"), str) or not dados[
        "arquivo_original"
    ].startswith("gs://"):
        raise ValueError("URI do original ausente")
    if not isinstance(dados.get("coleta_id"), str) or not dados["coleta_id"]:
        raise ValueError("coleta original ausente")
    for familia in sorted(familias):
        esperado = f"raw/tse/{familia}/{ano}/{dados['sha256_zip']}/dados.parquet"
        if dados["familias"][familia] != esperado:
            raise ValueError("caminho raw divergente")
        raw = _confinado(lago, esperado)
        if not raw.is_file():
            raise ValueError("arquivo raw ausente")
        if not all(_hash(dados[c][familia]) for c in ("hashes", "hashes_parquet")):
            raise ValueError("hash de família inválido")
        if sha256_arquivo(raw) != dados["hashes_parquet"][familia]:
            raise ValueError("hash Parquet divergente")
        if dados["layouts"][familia] != f"tse:{familia}:{ano}:v1":
            raise ValueError("layout não aprovado")
        if dados["membros"][familia] != f"{PREFIXOS[familia]}_{ano}_BRASIL.csv":
            raise ValueError("membro consolidado divergente")
        contagem = dados["contagens"][familia]
        if type(contagem) is not int or contagem < 0:
            raise ValueError("contagem inválida")
        nomes, _ = normalizar_cabecalho(list(LAYOUTS[familia, ano]))
        esquema = pa.schema([pa.field(n, pa.string()) for n in nomes] + CAMPOS_CONTROLE)
        with pq.ParquetFile(raw) as parquet:
            if not parquet.schema_arrow.equals(esquema, check_metadata=False):
                raise ValueError("schema/tipos Parquet divergentes do layout")
            if parquet.metadata.num_rows != contagem:
                raise ValueError("contagem Parquet divergente")
            geracoes = set()
            for lote in parquet.iter_batches(columns=["dt_geracao", "hh_geracao"]):
                geracoes.update(
                    zip(lote.column(0).to_pylist(), lote.column(1).to_pylist(), strict=True)
                )
            if dados["geracoes"][familia] != [list(g) for g in sorted(geracoes)]:
                raise ValueError("gerações do descritor divergentes")
    estrutural = _digest(
        {
            "recurso_id": recurso,
            "ano": ano,
            "sha256_zip": dados["sha256_zip"],
            "layouts": dados["layouts"],
            "membros": {f: f"{PREFIXOS[f]}_{{ano}}_BRASIL.csv" for f in familias},
        }
    )
    if rejeicoes_pendentes(
        lago,
        escopo="versao",
        identidade=versao_id,
        entradas_digest=estrutural,
        contrato="tse:estrutura:v1",
    ):
        raise ValueError("versão possui rejeição estrutural pendente")


def validar_selecao(lago: Path, selecao: SelecaoTse) -> tuple[str, ...]:
    """Retorna impedimentos sem promover ou confundir falhas operacionais com rejeições."""
    try:
        conferir_recuperacao(lago)
    except ErroRecuperacaoTse as erro:
        return (str(erro),)
    if not isinstance(selecao, SelecaoTse) or not isinstance(selecao.versoes, dict):
        return ("tipo de seleção inválido",)
    if not all(isinstance(k, str) and _hash(v) for k, v in selecao.versoes.items()):
        return ("chaves/identidades de versão inválidas",)
    if not _hash(selecao.selecao_id) or selecao.selecao_id != _digest(selecao.versoes):
        return ("identidade de seleção divergente",)
    if set(selecao.versoes) != COBERTURA:
        return ("cobertura deve conter três recursos × quatro anos",)
    impedimentos = []
    for chave, versao_id in sorted(selecao.versoes.items()):
        try:
            _validar_versao(lago, chave, versao_id)
        except (ValueError, KeyError, TypeError, OSError, pa.ArrowException) as erro:
            impedimentos.append(f"{chave}: {erro}")
    return tuple(impedimentos)


def _pasta_execucao(lago: Path, execucao_id: str) -> Path:
    if not isinstance(execucao_id, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", execucao_id
    ):
        raise ValueError("identidade de execução inválida")
    return _confinado(lago, f"estado/tse/publicacoes/preparadas/{execucao_id}")


def digest_saida(lago: Path, execucao_id: str) -> str:
    return _digest(inventario_saida(_pasta_execucao(lago, execucao_id) / "marts"))


def inventario_entradas(lago: Path, selecao: SelecaoTse) -> dict:
    """Inventário exato que a preparação T7 deve fixar antes de executar dbt."""
    entradas = {}
    for chave, versao_id in sorted(selecao.versoes.items()):
        caminho, dados = _descritor(lago, versao_id)
        entradas[chave] = {
            "versao_id": versao_id,
            "descritor": caminho.relative_to(lago).as_posix(),
            "sha256_descritor": sha256_arquivo(caminho),
            "familias": {
                f: {
                    "caminho": c,
                    "sha256": sha256_arquivo(_confinado(lago, c)),
                    "layout": dados["layouts"][f],
                    "sha256_csv": dados["hashes"][f],
                }
                for f, c in sorted(dados["familias"].items())
            },
        }
    return entradas


def vars_selecao(lago: Path, selecao: SelecaoTse, execucao_id: str) -> dict:
    """Caminhos absolutos explícitos para dbt; lista por família ordenada por ano."""
    fontes: dict[str, list[str]] = {}
    proveniencia: dict[str, dict] = {}
    for _chave, versao_id in sorted(selecao.versoes.items()):
        _, dados = _descritor(lago, versao_id)
        for familia, caminho in sorted(dados["familias"].items()):
            absoluto = _confinado(lago, caminho).resolve().as_posix()
            fontes.setdefault(familia, []).append(absoluto)
            proveniencia[absoluto] = {
                "ano_arquivo": dados["ano"],
                "versao_id": versao_id,
                "layout_id": dados["layouts"][familia],
            }
    return {
        "tse_contexto": {
            "selecao_id": selecao.selecao_id,
            "entradas_digest": digest_entradas(lago, selecao),
        },
        "tse_fontes": fontes,
        "tse_proveniencia": proveniencia,
        "tse_saida": (_pasta_execucao(lago, execucao_id) / "marts").resolve().as_posix(),
    }


def _ler_evidencia(lago, selecao, execucao_id, resultado):
    try:
        preparacao_path = _confinado(
            lago, f"estado/tse/publicacoes/preparadas/{execucao_id}/preparacao.json"
        )
        variaveis = json.loads(preparacao_path.read_bytes()).get("vars")
        obrigatorias = vars_selecao(lago, selecao, execucao_id)
        if not isinstance(variaveis, dict) or any(
            variaveis.get(k) != v for k, v in obrigatorias.items()
        ):
            raise ValueError("vars obrigatórias divergentes da seleção/saída")
        esperado = {
            "protocolo": PROTOCOLO_PREPARACAO,
            "execucao_id": execucao_id,
            "selecao": asdict(selecao),
            "selecao_digest": digest_selecao(selecao),
            "entradas": inventario_entradas(lago, selecao),
            "entradas_digest": digest_entradas(lago, selecao),
            "vars": variaveis,
            "vars_digest": _digest(variaveis),
            "saida": f"estado/tse/publicacoes/preparadas/{execucao_id}/marts",
            "contrato": CONTRATO,
        }
        return conferir_execucao(_pasta_execucao(lago, execucao_id), esperado, resultado)
    except (OSError, KeyError, TypeError, ValueError) as erro:
        raise ValueError(f"evidência de execução inválida: {erro}") from erro


def rejeicoes_conhecidas(lago: Path, selecao: SelecaoTse, entradas_digest: str) -> list[str]:
    """Histórico causal inteiro; aprovação por string não apaga uma rejeição posterior."""
    referencias = []
    for caminho in (lago / "estado/tse/validacoes").glob("*.json"):
        conteudo = caminho.read_bytes()
        if hashlib.sha256(conteudo).hexdigest() != caminho.stem:
            raise ValueError("integridade da avaliação divergente")
        dados = json.loads(conteudo)
        chave = {
            "escopo": "selecao",
            "identidade": selecao.selecao_id,
            "entradas_digest": entradas_digest,
            "contrato": CONTRATO,
            "resultado": "rejeitada",
        }
        if all(dados.get(k) == v for k, v in chave.items()):
            referencias.append(caminho.stem)
    return sorted(referencias)


def emitir_recibo(
    lago: Path,
    selecao: SelecaoTse,
    execucao_id: str,
    resultado: ResultadoDbt,
    *,
    superadas: tuple[str, ...] = (),
) -> ReciboValidacaoTse:
    """Emite após build completo selado; resultado isolado nunca autoriza promoção."""
    impedimentos = validar_selecao(lago, selecao)
    if impedimentos:
        raise ValueError("; ".join(impedimentos))
    if not isinstance(resultado, ResultadoDbt):
        raise ValueError("tipo de resultado dbt inválido")
    selo = _ler_evidencia(lago, selecao, execucao_id, resultado)
    recibo = ReciboValidacaoTse(
        digest_selecao(selecao),
        execucao_id,
        digest_entradas(lago, selecao),
        selo["saida_digest"],
        resultado,
    )
    pasta = _pasta_execucao(lago, execucao_id)
    caminho = pasta / "recibo.json"
    conhecidas = rejeicoes_conhecidas(lago, selecao, recibo.entradas_digest)
    if not all(_hash(ref) for ref in superadas) or sorted(superadas) != conhecidas:
        raise ValueError("novo recibo deve referenciar todas as rejeições conhecidas")
    dados = {
        "protocolo": "tse:recibo:v1",
        "recibo": asdict(recibo),
        "execucao_sha256": sha256_arquivo(pasta / "execucao.json"),
        "superadas": list(superadas),
        "rejeicoes_conhecidas": conhecidas,
    }
    evidencia = _digest(dados)
    dados["evidencia"] = evidencia
    if caminho.exists():
        if json.loads(caminho.read_bytes()) != dados:
            raise ValueError("recibo imutável já existe; nova avaliação exige nova execução")
    gravar_avaliacao(
        lago,
        escopo="selecao",
        identidade=selecao.selecao_id,
        entradas_digest=recibo.entradas_digest,
        contrato=CONTRATO,
        execucao_id=execucao_id,
        resultado="aprovada",
        motivos=[],
        superadas=superadas,
        evidencia=evidencia,
    )
    if not caminho.exists():
        gravar_json(caminho, dados)
    return recibo


def conferir_recibo_tse(lago: Path, selecao: SelecaoTse, recibo: ReciboValidacaoTse) -> None:
    """Confere evidência física e causal atual sem gravar seletores ou avaliações."""
    conferir_recuperacao(lago)
    impedimentos = validar_selecao(lago, selecao)
    if impedimentos:
        raise ValueError("; ".join(impedimentos))
    if not isinstance(recibo, ReciboValidacaoTse) or recibo.selecao_digest != digest_selecao(
        selecao
    ):
        raise ValueError("recibo de outra seleção")
    if recibo.entradas_digest != digest_entradas(lago, selecao):
        raise ValueError("entradas alteradas após validação")
    selo = _ler_evidencia(lago, selecao, recibo.execucao_id, recibo.resultado)
    if recibo.saida_digest != digest_saida(lago, recibo.execucao_id):
        raise ValueError("saída alterada após validação")
    pasta = _pasta_execucao(lago, recibo.execucao_id)
    try:
        dados = json.loads(
            _confinado(
                lago, f"estado/tse/publicacoes/preparadas/{recibo.execucao_id}/recibo.json"
            ).read_bytes()
        )
    except (OSError, ValueError) as erro:
        raise ValueError("recibo persistido ausente ou inválido") from erro
    evidencia = _digest({k: v for k, v in dados.items() if k != "evidencia"})
    if (
        dados.get("protocolo") != "tse:recibo:v1"
        or dados.get("recibo") != asdict(recibo)
        or dados.get("evidencia") != evidencia
        or dados.get("execucao_sha256") != sha256_arquivo(pasta / "execucao.json")
        or selo["saida_digest"] != recibo.saida_digest
    ):
        raise ValueError("recibo persistido divergente")
    referencias = dados.get("superadas")
    if (
        not isinstance(referencias, list)
        or not all(_hash(ref) for ref in referencias)
        or sorted(referencias) != dados.get("rejeicoes_conhecidas")
    ):
        raise ValueError("recibo não referencia explicitamente todas as rejeições conhecidas")
    if dados.get("rejeicoes_conhecidas") != rejeicoes_conhecidas(
        lago, selecao, recibo.entradas_digest
    ):
        raise ValueError("rejeição posterior exige nova execução/recibo completo")
    if rejeicoes_pendentes(
        lago,
        escopo="selecao",
        identidade=selecao.selecao_id,
        entradas_digest=recibo.entradas_digest,
        contrato=CONTRATO,
    ):
        raise ValueError("seleção possui rejeição pendente; exige nova avaliação completa")
    chave_aprovacao = {
        "escopo": "selecao",
        "identidade": selecao.selecao_id,
        "entradas_digest": recibo.entradas_digest,
        "contrato": CONTRATO,
        "execucao_id": recibo.execucao_id,
        "resultado": "aprovada",
        "evidencia": evidencia,
    }
    aprovada = False
    for caminho in (lago / "estado/tse/validacoes").glob("*.json"):
        confinado = _confinado(lago, caminho.relative_to(lago).as_posix())
        if confinado.is_symlink():
            raise ValueError("avaliação fora do histórico privado")
        conteudo = confinado.read_bytes()
        if hashlib.sha256(conteudo).hexdigest() != caminho.stem:
            raise ValueError("integridade da avaliação divergente")
        avaliacao = json.loads(conteudo)
        if all(avaliacao.get(k) == v for k, v in chave_aprovacao.items()) and sorted(
            avaliacao.get("superadas", [])
        ) == sorted(referencias):
            aprovada = True
    if not aprovada:
        raise ValueError("seleção sem aprovação concreta vinculada ao recibo atual")


def promover_selecao(lago: Path, selecao: SelecaoTse, recibo: ReciboValidacaoTse) -> None:
    """Troca seletor completo; compensa falhas ou bloqueia recuperação incerta."""
    conferir_recibo_tse(lago, selecao, recibo)
    estado = _confinado(lago, "estado/tse")
    selecoes = _confinado(lago, f"estado/tse/selecoes/{selecao.selecao_id}.json")
    if selecoes.exists():
        if json.loads(selecoes.read_bytes()) != asdict(selecao):
            raise ValueError("colisão de seleção imutável")
    else:
        gravar_json(selecoes, asdict(selecao))
    marcador = _confinado(lago, "estado/tse/inicializado.json")
    if marcador.exists():
        if json.loads(marcador.read_bytes()).get("protocolo") != "tse:inicializado:v1":
            raise ValueError("marcador de inicialização inválido")
    else:
        # Persiste antes do seletor: interrupção conservadora nunca reabre bootstrap legado.
        gravar_json(
            marcador,
            {"protocolo": "tse:inicializado:v1", "primeira_selecao_id": selecao.selecao_id},
        )
    with pasta_temporaria("tse-seletor-") as pasta:
        origem = Path(pasta) / "vigente.json"
        origem.write_text(json_canonico(asdict(selecao)), encoding="utf-8")
        instalar_com_compensacao(lago, [(origem, estado / "vigente.json")])
