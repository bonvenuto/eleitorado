import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from coletor.publicacao import CACHE_SITE, ErroPublicacao, publicar

AGORA = datetime(2026, 10, 4, 10, tzinfo=UTC)


class FakePublicador:
    """Bucket em memória: guarda o conteúdo e devolve o MD5 como ETag, como o R2."""

    def __init__(self, existentes: dict[str, bytes] | None = None) -> None:
        self.objetos: dict[str, bytes] = dict(existentes or {})
        self.atributos: dict[str, tuple[str, str | None, str | None]] = {}
        self.ordem: list[tuple[str, str]] = []
        self.manifesto: dict | None = None

    def listar(self) -> dict[str, str]:
        return {chave: hashlib.md5(dados).hexdigest() for chave, dados in self.objetos.items()}

    def enviar(self, origem, chave, tipo, codificacao=None, cache=None) -> None:
        self.ordem.append(("enviar", chave))
        self.objetos[chave] = Path(origem).read_bytes()
        self.atributos[chave] = (tipo, codificacao, cache)
        if chave == "manifesto.json":
            self.manifesto = json.loads(self.objetos[chave])

    def apagar(self, chave: str) -> None:
        self.ordem.append(("apagar", chave))
        self.objetos.pop(chave, None)

    @property
    def chaves(self) -> set[str]:
        return set(self.objetos)


@pytest.fixture
def publico(tmp_path):
    raiz = tmp_path / "publico"
    (raiz / "marts" / "fct" / "casa=camara").mkdir(parents=True)
    pq.write_table(pa.table({"a": [1, 2, 3]}), raiz / "marts" / "dim_uf.parquet")
    pq.write_table(pa.table({"a": [1]}), raiz / "marts" / "fct" / "casa=camara" / "d.parquet")
    (raiz / "linhagem").mkdir()
    (raiz / "linhagem" / "index.html").write_text("<html></html>")
    return raiz


def _site(publico: Path, arquivos: dict[str, bytes]) -> None:
    for caminho, dados in arquivos.items():
        destino = publico / "site" / caminho
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(dados)


def test_envia_marts_e_linhagem_e_o_manifesto_por_ultimo(publico):
    publicador = FakePublicador()
    resumo = publicar(publicador, publico, AGORA, "abc123")
    assert publicador.ordem[-1] == ("enviar", "manifesto.json")
    assert resumo.enviados == 4
    arquivos = {a["caminho"]: a for a in publicador.manifesto["arquivos"]}
    assert set(arquivos) == {
        "linhagem/index.html",
        "marts/dim_uf.parquet",
        "marts/fct/casa=camara/d.parquet",
    }
    assert arquivos["marts/dim_uf.parquet"]["linhas"] == 3
    assert arquivos["linhagem/index.html"]["linhas"] is None
    assert len(arquivos["marts/dim_uf.parquet"]["sha256"]) == 64
    assert publicador.manifesto["versao"] == "abc123"


def test_apaga_o_que_deixou_de_existir_depois_do_manifesto(publico):
    publicador = FakePublicador({"marts/antigo.parquet": b"x", "manifesto.json": b"{}"})
    resumo = publicar(publicador, publico, AGORA, "v")
    assert resumo.apagados == 1
    posicao_manifesto = publicador.ordem.index(("enviar", "manifesto.json"))
    assert publicador.ordem.index(("apagar", "marts/antigo.parquet")) > posicao_manifesto
    assert "manifesto.json" in publicador.chaves


def test_arquivo_fora_dos_caminhos_permitidos_impede_a_publicacao(publico):
    (publico / "raw").mkdir()
    (publico / "raw" / "cpfs.parquet").write_bytes(b"x")
    publicador = FakePublicador()
    with pytest.raises(ErroPublicacao, match="raw/cpfs.parquet"):
        publicar(publicador, publico, AGORA, "v")
    assert publicador.ordem == []


def test_sem_marts_nada_e_publicado(tmp_path):
    vazio = tmp_path / "publico"
    (vazio / "linhagem").mkdir(parents=True)
    (vazio / "linhagem" / "index.html").write_text("x")
    publicador = FakePublicador({"marts/dim_uf.parquet": b"x"})
    with pytest.raises(ErroPublicacao, match="nenhum mart"):
        publicar(publicador, vazio, AGORA, "v")
    assert publicador.ordem == []


def test_so_envia_o_que_mudou(publico):
    publicador = FakePublicador()
    publicar(publicador, publico, AGORA, "v")
    publicador.ordem.clear()
    (publico / "linhagem" / "index.html").write_text("<html>nova</html>")

    resumo = publicar(publicador, publico, AGORA, "v")

    assert publicador.ordem == [("enviar", "linhagem/index.html"), ("enviar", "manifesto.json")]
    assert resumo.enviados == 2
    assert resumo.inalterados == 2


def test_site_vai_em_gzip_com_cache_e_fica_fora_do_manifesto(publico):
    _site(publico, {"resumo.json": b"\x1f\x8b gzip"})
    publicador = FakePublicador()
    publicar(publicador, publico, AGORA, "v")
    assert publicador.atributos["site/resumo.json"] == ("application/json", "gzip", CACHE_SITE)
    assert publicador.atributos["marts/dim_uf.parquet"][1:] == (None, None)
    caminhos = {a["caminho"] for a in publicador.manifesto["arquivos"]}
    assert not any(c.startswith("site/") for c in caminhos)


def test_sem_site_local_o_site_do_bucket_fica(publico):
    publicador = FakePublicador({"site/resumo.json": b"anterior", "marts/antigo.parquet": b"x"})
    resumo = publicar(publicador, publico, AGORA, "v")
    assert publicador.objetos["site/resumo.json"] == b"anterior"
    assert "marts/antigo.parquet" not in publicador.chaves
    assert resumo.apagados == 1


def test_com_site_local_apaga_o_arquivo_de_site_que_sumiu(publico):
    _site(publico, {"resumo.json": b"novo"})
    publicador = FakePublicador({"site/resumo.json": b"anterior", "site/empresa/999.json": b"x"})
    publicar(publicador, publico, AGORA, "v")
    assert publicador.objetos["site/resumo.json"] == b"novo"
    assert "site/empresa/999.json" not in publicador.chaves


def test_etag_que_nao_e_md5_faz_reenviar(publico):
    # objeto enviado antes em multipart: o ETag ("<hash>-<partes>") nunca bate com o MD5
    class Multipart(FakePublicador):
        def listar(self) -> dict[str, str]:
            return {chave: "abc-2" for chave in self.objetos}

    publicador = Multipart()
    publicar(publicador, publico, AGORA, "v")
    publicador.ordem.clear()
    publicar(publicador, publico, AGORA, "v")
    assert ("enviar", "marts/dim_uf.parquet") in publicador.ordem


def test_envia_em_paralelo(publico):
    import threading
    import time

    _site(publico, {f"parlamentar/camara-{i}.json": bytes([i]) for i in range(8)})

    class Lento(FakePublicador):
        def __init__(self) -> None:
            super().__init__()
            self.trava = threading.Lock()
            self.agora = 0
            self.maximo = 0

        def enviar(self, origem, chave, tipo, codificacao=None, cache=None) -> None:
            with self.trava:
                self.agora += 1
                self.maximo = max(self.maximo, self.agora)
            time.sleep(0.05)
            super().enviar(origem, chave, tipo, codificacao, cache)
            with self.trava:
                self.agora -= 1

    publicador = Lento()
    publicar(publicador, publico, AGORA, "v")
    assert publicador.maximo > 1
    assert publicador.ordem[-1] == ("enviar", "manifesto.json")
    assert len(publicador.chaves) == 12  # 3 de marts/linhagem, 8 do site e o manifesto


def test_r2_sem_checksum_no_trailer(monkeypatch):
    # com o checksum em trailer, o botocore manda "Content-Encoding: gzip,aws-chunked"
    import boto3

    from coletor.publicacao import R2Publicador

    vistos = {}
    monkeypatch.setattr(boto3, "client", lambda *a, **k: vistos.update(k) or object())
    R2Publicador("conta", "id", "segredo", "bucket")
    assert vistos["config"].request_checksum_calculation == "when_required"
    assert vistos["config"].response_checksum_validation == "when_required"
