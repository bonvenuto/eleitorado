"""Publicação C2: evidência concreta, bytes remotos e edições preservadas, sem rede."""

import hashlib
import io
import json
import shutil
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from botocore.exceptions import ClientError
from botocore.response import StreamingBody

from coletor.dbt import ResultadoDbt
from coletor.hashes import json_canonico, sha256_arquivo
from coletor.publicacao import ErroPublicacao, R2Publicador
from coletor.tse.evidencias import inventario_saida
from coletor.tse.execucao import preparar_execucao_tse
from coletor.tse.publicacao import publicar_tse
from coletor.tse.selecao import digest_saida, emitir_recibo
from coletor.tse.validacoes import gravar_avaliacao
from tests.amostras import AGORA
from tests.test_tse_selecao import montar_vetor

ARQUIVOS = {
    "dim_candidatura.parquet": {
        "candidatura_id",
        "cd_eleicao",
        "sq_candidato",
        "data_eleicao",
        "cargo_codigo",
        "cargo",
        "uf_sigla",
        "localidade_codigo",
        "localidade",
        "nome_publico",
        "partido_numero",
        "partido_sigla",
        "situacao_eleitoral",
    },
    "fct_receita_campanha_resumo.parquet": {
        "candidatura_id",
        "natureza_recurso",
        "origem_recurso",
        "valor",
        "quantidade",
    },
    "fct_despesa_campanha_pj.parquet": {
        "despesa_id",
        "candidatura_id",
        "tipo_fato",
        "fornecedor_cnpj",
        "data",
        "valor",
    },
    "fct_patrimonio_declarado.parquet": {
        "candidatura_id",
        "tipo_bem_codigo",
        "quantidade",
        "valor",
    },
    "monitor_tse.parquet": {
        "cobertura",
        "auditoria",
        "selecao_id",
        "entradas_id",
        "ano_arquivo",
        "layout_id",
        "prazo_dias",
        "familia",
        "rechecado_em",
        "versao_id",
    },
}
MANIFESTO = "marts/c2/manifesto.json"


class PublicadorMemoria:
    """Bytes armazenados são independentes do arquivo local depois do envio."""

    def __init__(self):
        self.objetos = {MANIFESTO: b"manifesto anterior"}
        self.eventos = []
        self.falhar = None
        self.corromper = False

    def listar(self):
        return set(self.objetos)

    def enviar(self, origem, chave, tipo):
        self.eventos.append(("enviar", chave))
        if chave == self.falhar or (self.falhar == "arquivo" and chave != MANIFESTO):
            raise OSError("upload indisponível")
        self.objetos[chave] = origem.read_bytes()
        if self.corromper and chave != MANIFESTO:
            self.objetos[chave] = b"bytes remotos errados"

    def conferir(self, chave, sha256, bytes):
        self.eventos.append(("conferir", chave))
        conteudo = self.objetos.get(chave, b"")
        return len(conteudo) == bytes and hashlib.sha256(conteudo).hexdigest() == sha256

    def apagar(self, chave):
        raise AssertionError(f"C2 nunca apaga {chave}")


def selar(lago, selecao, pasta):
    """Artefatos concretos sintéticos do controlador: nenhum subprocesso dbt inventado."""
    preparacao = json.loads((pasta / "preparacao.json").read_bytes())
    variaveis = preparacao["vars"]
    nodes = {}
    for arquivo in ARQUIVOS:
        nome = arquivo.removesuffix(".parquet")
        nodes[f"model.tse.{nome}"] = {"resource_type": "model", "config": {"enabled": True}}
        for teste in ("sem_cpf_completo", "sem_dados_pessoais"):
            nodes[f"test.tse.{teste}_{nome}"] = {
                "resource_type": "test",
                "config": {"enabled": True},
            }
    resultados = [
        {"unique_id": chave, "status": "pass" if no["resource_type"] == "test" else "success"}
        for chave, no in nodes.items()
    ]
    manifesto = {"metadata": {"invocation_id": "dbt-publicacao"}, "nodes": nodes}
    run_results = {
        "metadata": {"invocation_id": "dbt-publicacao"},
        "args": {"which": "build", "target": "ci", "vars": variaveis},
        "results": resultados,
    }
    for nome, dados in (("manifest", manifesto), ("run_results", run_results)):
        (pasta / f"{nome}.json").write_text(json_canonico(dados), encoding="utf-8")
    selo = {
        "protocolo": "tse:execucao:v1",
        "execucao_id": pasta.name,
        "preparacao_sha256": sha256_arquivo(pasta / "preparacao.json"),
        "invocation_id": "dbt-publicacao",
        "manifest_sha256": sha256_arquivo(pasta / "manifest.json"),
        "run_results_sha256": sha256_arquivo(pasta / "run_results.json"),
        "selecao_digest": preparacao["selecao_digest"],
        "entradas_digest": preparacao["entradas_digest"],
        "vars_digest": preparacao["vars_digest"],
        "saida": inventario_saida(pasta / "marts"),
        "saida_digest": digest_saida(lago, pasta.name),
        "comando": ["dbt", "build", "--target", "ci", "--vars", json_canonico(variaveis)],
        "retorno": 0,
        "resultado": asdict(ResultadoDbt("sucesso", 0)),
    }
    (pasta / "execucao.json").write_text(json_canonico(selo), encoding="utf-8")
    return emitir_recibo(lago, selecao, pasta.name, ResultadoDbt("sucesso", 0))


def candidata(lago, selecao, nome="publicacao-1", alterar=None):
    preparada = preparar_execucao_tse(lago, nome, "ci", selecao).saida
    for arquivo, colunas in ARQUIVOS.items():
        tabela = pa.table({coluna: pa.array([], type=pa.string()) for coluna in sorted(colunas)})
        pq.write_table(tabela, preparada / arquivo)
    if alterar:
        alterar(preparada)
    recibo = selar(lago, selecao, preparada.parent)
    return preparada, selecao, recibo


@pytest.fixture
def validada(tmp_path):
    lago, selecao = montar_vetor(tmp_path)
    return candidata(lago, selecao)


def publicar(publicador, validada, **extras):
    preparada, selecao, recibo = validada
    return publicar_tse(
        publicador,
        preparada,
        selecao,
        extras.get("gerado_em", AGORA),
        extras.get("versao", "codigo-v1"),
        extras.get("recibo", recibo),
    )


def test_falha_upload_conserva_manifesto(validada):
    remoto = PublicadorMemoria()
    remoto.falhar = "arquivo"
    with pytest.raises(OSError, match="upload"):
        publicar(remoto, validada)
    assert remoto.objetos[MANIFESTO] == b"manifesto anterior"
    assert ("enviar", MANIFESTO) not in remoto.eventos


def test_conferencia_bytes_errados_conserva_manifesto(validada):
    remoto = PublicadorMemoria()
    remoto.corromper = True
    with pytest.raises(ErroPublicacao, match="confer|bytes"):
        publicar(remoto, validada)
    assert remoto.objetos[MANIFESTO] == b"manifesto anterior"
    assert ("enviar", MANIFESTO) not in remoto.eventos


def test_manifesto_apos_todos_bytes_conferidos(validada):
    remoto = PublicadorMemoria()
    resumo = publicar(remoto, validada)
    assert [e for e in remoto.eventos if e[0] == "enviar"][-1] == ("enviar", MANIFESTO)
    assert len([e for e in remoto.eventos if e[0] == "conferir" and e[1] != MANIFESTO]) == 5
    assert resumo.enviados == 6 and resumo.apagados == 0
    manifesto = json.loads(remoto.objetos[MANIFESTO])
    assert len(manifesto["edicao_id"]) == 64
    assert {Path(a["caminho"]).name for a in manifesto["arquivos"]} == set(ARQUIVOS)
    for item in manifesto["arquivos"]:
        conteudo = remoto.objetos[item["caminho"]]
        assert item["sha256"] == hashlib.sha256(conteudo).hexdigest()
        assert item["bytes"] == len(conteudo)


def test_repetir_edicao_idempotente(validada):
    remoto = PublicadorMemoria()
    publicar(remoto, validada)
    edicao = json.loads(remoto.objetos[MANIFESTO])["edicao_id"]
    arquivos = {k: v for k, v in remoto.objetos.items() if k != MANIFESTO}
    remoto.eventos.clear()
    resumo = publicar(remoto, validada, gerado_em=AGORA + timedelta(days=1))
    assert json.loads(remoto.objetos[MANIFESTO])["edicao_id"] == edicao
    assert {k: v for k, v in remoto.objetos.items() if k != MANIFESTO} == arquivos
    assert [e for e in remoto.eventos if e[0] == "enviar"] == [("enviar", MANIFESTO)]
    assert resumo.enviados == 1 and resumo.apagados == 0


def test_colisao_edicao_nunca_sobrescreve(validada):
    remoto = PublicadorMemoria()
    publicar(remoto, validada)
    chave = next(k for k in remoto.objetos if k.endswith("dim_candidatura.parquet"))
    remoto.objetos[chave] = b"colisao"
    remoto.eventos.clear()
    anterior = remoto.objetos[MANIFESTO]
    with pytest.raises(ErroPublicacao, match="colis|imut"):
        publicar(remoto, validada)
    assert remoto.objetos[chave] == b"colisao"
    assert remoto.objetos[MANIFESTO] == anterior
    assert not any(e[0] == "enviar" for e in remoto.eventos)


def test_rollback_reponta_edicao_verificada(validada):
    remoto = PublicadorMemoria()
    publicar(remoto, validada)
    primeira = json.loads(remoto.objetos[MANIFESTO])["edicao_id"]
    publicar(remoto, validada, versao="codigo-v2")
    segunda = json.loads(remoto.objetos[MANIFESTO])["edicao_id"]
    assert primeira != segunda
    anteriores = set(remoto.objetos)
    remoto.eventos.clear()
    publicar(remoto, validada)
    assert json.loads(remoto.objetos[MANIFESTO])["edicao_id"] == primeira
    assert set(remoto.objetos) == anteriores
    assert [e for e in remoto.eventos if e[0] == "enviar"] == [("enviar", MANIFESTO)]
    assert len([e for e in remoto.eventos if e[0] == "conferir" and e[1] != MANIFESTO]) == 5


@pytest.mark.parametrize("defeito", ["recibo", "aprovacao", "selo", "saida", "entrada"])
def test_evidencia_persistida_obrigatoria(validada, defeito):
    preparada, selecao, recibo = validada
    lago = preparada.parents[5]
    if defeito == "recibo":
        (preparada.parent / "recibo.json").unlink()
    elif defeito == "aprovacao":
        for p in (lago / "estado/tse/validacoes").glob("*.json"):
            p.unlink()
    elif defeito == "selo":
        (preparada.parent / "execucao.json").write_bytes(b"{}")
    elif defeito == "saida":
        (preparada / "dim_candidatura.parquet").write_bytes(b"mudou")
    else:
        raw = next((lago / "raw/tse").rglob("*.parquet"))
        raw.write_bytes(b"mudou")
    remoto = PublicadorMemoria()
    with pytest.raises((ValueError, ErroPublicacao)):
        publicar(remoto, validada)
    assert remoto.eventos == []


def test_rejeicao_posterior_bloqueia_recibo_anterior(validada):
    preparada, selecao, recibo = validada
    lago = preparada.parents[5]
    gravar_avaliacao(
        lago,
        escopo="selecao",
        identidade=selecao.selecao_id,
        entradas_digest=recibo.entradas_digest,
        contrato="tse:selecao:v1",
        execucao_id="rejeicao-nova",
        resultado="rejeitada",
        motivos=[],
    )
    remoto = PublicadorMemoria()
    with pytest.raises(ValueError, match="rejei"):
        publicar(remoto, validada)
    assert remoto.eventos == []


def test_recibo_de_outra_execucao_bloqueado(validada):
    remoto = PublicadorMemoria()
    with pytest.raises(ValueError):
        publicar(remoto, validada, recibo=replace(validada[2], execucao_id="outra"))
    assert remoto.eventos == []


def test_preparada_fora_layout_bloqueada(validada, tmp_path):
    preparada, selecao, recibo = validada
    arbitraria = tmp_path / "marts"
    shutil.copytree(preparada, arbitraria)
    remoto = PublicadorMemoria()
    with pytest.raises(ValueError, match="preparad|layout|caminho"):
        publicar_tse(remoto, arbitraria, selecao, AGORA, "v", recibo)
    assert remoto.eventos == []


@pytest.mark.parametrize("defeito", ["arquivo_extra", "coluna_privada", "arquivo_ausente"])
def test_allowlist_fechada_mesmo_com_recibo_verde(tmp_path, defeito):
    lago, selecao = montar_vetor(tmp_path)

    def alterar(pasta):
        if defeito == "arquivo_extra":
            (pasta / "monitor_arbitrario.parquet").write_bytes(b"nao aprovado ainda")
        elif defeito == "coluna_privada":
            arquivo = pasta / "dim_candidatura.parquet"
            tabela = pq.read_table(arquivo).append_column(
                "linha_original", pa.array([], pa.string())
            )
            pq.write_table(tabela, arquivo)
        else:
            (pasta / "dim_candidatura.parquet").unlink()

    validada = candidata(lago, selecao, alterar=alterar)
    remoto = PublicadorMemoria()
    with pytest.raises(ErroPublicacao, match="allowlist|coluna|arquivo"):
        publicar(remoto, validada)
    assert remoto.eventos == []


def test_get_streaming_reprova_bytes_errados_mesmo_etag():
    esperado = b"conteudo autorizado"
    fluxo = io.BytesIO(b"conteudo adulterado")
    corpo = StreamingBody(fluxo, len(b"conteudo adulterado"))

    class S3:
        def get_object(self, **kwargs):
            assert kwargs == {"Bucket": "teste", "Key": "marts/c2/arquivo"}
            return {
                "Body": corpo,
                "ETag": hashlib.md5(esperado).hexdigest(),
                "Metadata": {"sha256": hashlib.sha256(esperado).hexdigest()},
                "ContentLength": len(esperado),
            }

    remoto = object.__new__(R2Publicador)
    remoto._bucket, remoto._s3 = "teste", S3()
    assert not remoto.conferir(
        "marts/c2/arquivo", hashlib.sha256(esperado).hexdigest(), len(esperado)
    )
    assert fluxo.closed


def test_get_streaming_confere_todos_blocos():
    conteudo = b"a" * (2 * 1024 * 1024 + 17)

    class Corpo(io.BytesIO):
        def read(self, tamanho=-1):
            assert 0 < tamanho <= 1024 * 1024
            return super().read(tamanho)

    corpo = Corpo(conteudo)

    class S3:
        def get_object(self, **kwargs):
            return {"Body": corpo, "ETag": "multipart-2"}

    remoto = object.__new__(R2Publicador)
    remoto._bucket, remoto._s3 = "teste", S3()
    assert remoto.conferir("arquivo", hashlib.sha256(conteudo).hexdigest(), len(conteudo))
    assert corpo.closed


def test_get_ausente_diferente_de_falha_operacional():
    class S3:
        def get_object(self, **kwargs):
            raise ClientError({"Error": {"Code": self.codigo}}, "GetObject")

    remoto = object.__new__(R2Publicador)
    remoto._bucket, remoto._s3 = "teste", S3()
    remoto._s3.codigo = "NoSuchKey"
    assert not remoto.conferir("ausente", "0" * 64, 0)
    remoto._s3.codigo = "AccessDenied"
    with pytest.raises(ClientError):
        remoto.conferir("proibido", "0" * 64, 0)


def test_manifesto_aceito_com_ack_incerto_aponta_edicao_integra(validada):
    from coletor.tse.publicacao import ErroManifestoIncerto

    class Incerto(PublicadorMemoria):
        def enviar(self, origem, chave, tipo):
            super().enviar(origem, chave, tipo)
            if chave == MANIFESTO:
                raise OSError("ACK perdido depois da aceitação")

    remoto = Incerto()
    with pytest.raises(ErroManifestoIncerto) as erro:
        publicar(remoto, validada)
    manifesto = json.loads(remoto.objetos[MANIFESTO])
    assert erro.value.edicao_id == manifesto["edicao_id"]
    assert erro.value.manifesto == MANIFESTO
    for item in manifesto["arquivos"]:
        assert remoto.conferir(item["caminho"], item["sha256"], item["bytes"])


def test_r2_cache_c2_preserva_metadados_legados(tmp_path):
    arquivo = tmp_path / "arquivo"
    arquivo.write_bytes(b"teste")
    envios = []

    class S3:
        def upload_file(self, origem, bucket, chave, ExtraArgs):
            envios.append((chave, ExtraArgs))

    remoto = object.__new__(R2Publicador)
    remoto._bucket, remoto._s3 = "teste", S3()
    remoto.enviar(arquivo, MANIFESTO, "application/json")
    remoto.enviar(arquivo, "marts/c2/edicoes/id/a.parquet", "application/vnd.apache.parquet")
    remoto.enviar(arquivo, "manifesto.json", "application/json")
    assert envios[0][1] == {"ContentType": "application/json", "CacheControl": "no-cache"}
    assert envios[1][1] == {
        "ContentType": "application/vnd.apache.parquet",
        "CacheControl": "public, max-age=31536000, immutable",
    }
    assert envios[2][1] == {"ContentType": "application/json"}


def test_traversal_na_preparada_bloqueado(validada):
    preparada, selecao, recibo = validada
    remoto = PublicadorMemoria()
    caminho = preparada / ".." / "marts"
    with pytest.raises(ValueError, match="canonic|caminho|preparad"):
        publicar_tse(remoto, caminho, selecao, AGORA, "v", recibo)
    assert remoto.eventos == []


def test_edicao_independe_de_execucao_e_relogio(validada):
    preparada, selecao, recibo = validada
    remoto = PublicadorMemoria()
    publicar(remoto, validada)
    primeira = json.loads(remoto.objetos[MANIFESTO])["edicao_id"]
    outra = candidata(preparada.parents[5], selecao, nome="publicacao-2")
    remoto.eventos.clear()
    publicar(remoto, outra, gerado_em=AGORA + timedelta(days=1))
    assert json.loads(remoto.objetos[MANIFESTO])["edicao_id"] == primeira
    assert [e for e in remoto.eventos if e[0] == "enviar"] == [("enviar", MANIFESTO)]


def test_get_usa_hash_autorizado_se_local_mudar_durante_upload(validada):
    class Muda(PublicadorMemoria):
        def enviar(self, origem, chave, tipo):
            if chave != MANIFESTO:
                origem.write_bytes(b"alteracao depois da validacao")
            super().enviar(origem, chave, tipo)

    remoto = Muda()
    with pytest.raises(ErroPublicacao, match="conferência de bytes"):
        publicar(remoto, validada)
    assert remoto.objetos[MANIFESTO] == b"manifesto anterior"
    assert ("enviar", MANIFESTO) not in remoto.eventos


def test_rechecagem_causal_antes_do_manifesto(validada):
    preparada, selecao, recibo = validada

    class Rejeita(PublicadorMemoria):
        def enviar(self, origem, chave, tipo):
            super().enviar(origem, chave, tipo)
            if len(self.eventos) == 1:
                gravar_avaliacao(
                    preparada.parents[5],
                    escopo="selecao",
                    identidade=selecao.selecao_id,
                    entradas_digest=recibo.entradas_digest,
                    contrato="tse:selecao:v1",
                    execucao_id="posterior",
                    resultado="rejeitada",
                    motivos=[],
                )

    remoto = Rejeita()
    with pytest.raises(ValueError, match="rejei"):
        publicar(remoto, validada)
    assert remoto.objetos[MANIFESTO] == b"manifesto anterior"
    assert ("enviar", MANIFESTO) not in remoto.eventos


def test_objeto_extra_no_mesmo_prefixo_edicao_bloqueia(validada):
    remoto = PublicadorMemoria()
    publicar(remoto, validada)
    edicao = json.loads(remoto.objetos[MANIFESTO])["edicao_id"]
    chave = f"marts/c2/edicoes/{edicao}/extra.parquet"
    remoto.objetos[chave] = b"nao autorizado"
    remoto.eventos.clear()
    with pytest.raises(ErroPublicacao, match="colisão"):
        publicar(remoto, validada)
    assert remoto.eventos == []
    assert remoto.objetos[chave] == b"nao autorizado"


def test_put_manifesto_falha_antes_escrita_conserva_anterior(validada):
    from coletor.tse.publicacao import ErroManifestoIncerto

    remoto = PublicadorMemoria()
    remoto.falhar = MANIFESTO
    with pytest.raises(ErroManifestoIncerto):
        publicar(remoto, validada)
    assert remoto.objetos[MANIFESTO] == b"manifesto anterior"


def test_get_manifesto_sem_confirmacao_retorna_resultado_incerto(validada):
    from coletor.tse.publicacao import ErroManifestoIncerto

    class SemConfirmacao(PublicadorMemoria):
        def conferir(self, chave, sha256, bytes):
            if chave == MANIFESTO:
                return False
            return super().conferir(chave, sha256, bytes)

    remoto = SemConfirmacao()
    with pytest.raises(ErroManifestoIncerto):
        publicar(remoto, validada)


def test_rollback_entre_selecoes_nao_muda_vigente(tmp_path):
    from coletor.tse.selecao import criar_selecao, promover_selecao
    from tests.test_tse_selecao import versao

    lago, primeira = montar_vetor(tmp_path)
    antiga = candidata(lago, primeira, "edicao-antiga")
    promover_selecao(lago, primeira, antiga[2])
    nova = versao(lago, tmp_path / "retificada", "bens", 2024, total=80)
    segunda = criar_selecao({**primeira.versoes, "tse.bens:2024": nova.versao_id})
    atual = candidata(lago, segunda, "edicao-atual")
    promover_selecao(lago, segunda, atual[2])
    vigente = (lago / "estado/tse/vigente.json").read_bytes()
    remoto = PublicadorMemoria()
    publicar(remoto, antiga)
    edicao_antiga = json.loads(remoto.objetos[MANIFESTO])["edicao_id"]
    publicar(remoto, atual)
    edicao_atual = json.loads(remoto.objetos[MANIFESTO])["edicao_id"]
    assert edicao_atual != edicao_antiga
    anteriores = set(remoto.objetos)
    publicar(remoto, antiga)
    assert json.loads(remoto.objetos[MANIFESTO])["edicao_id"] == edicao_antiga
    assert (lago / "estado/tse/vigente.json").read_bytes() == vigente
    assert json.loads(vigente)["selecao_id"] == segunda.selecao_id
    assert set(remoto.objetos) == anteriores
