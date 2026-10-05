import json
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from coletor.publicacao import ErroPublicacao, publicar

AGORA = datetime(2026, 10, 4, 10, tzinfo=UTC)


class FakePublicador:
    def __init__(self, existentes: set[str] | None = None) -> None:
        self.chaves = set(existentes or set())
        self.ordem: list[tuple[str, str]] = []
        self.manifesto: dict | None = None

    def listar(self) -> set[str]:
        return set(self.chaves)

    def enviar(self, origem: Path, chave: str, tipo: str) -> None:
        self.ordem.append(("enviar", chave))
        self.chaves.add(chave)
        if chave == "manifesto.json":
            self.manifesto = json.loads(origem.read_text(encoding="utf-8"))

    def apagar(self, chave: str) -> None:
        self.ordem.append(("apagar", chave))
        self.chaves.discard(chave)


@pytest.fixture
def publico(tmp_path):
    raiz = tmp_path / "publico"
    (raiz / "marts" / "fct" / "casa=camara").mkdir(parents=True)
    pq.write_table(pa.table({"a": [1, 2, 3]}), raiz / "marts" / "dim_uf.parquet")
    pq.write_table(pa.table({"a": [1]}), raiz / "marts" / "fct" / "casa=camara" / "d.parquet")
    (raiz / "linhagem").mkdir()
    (raiz / "linhagem" / "index.html").write_text("<html></html>")
    return raiz


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
    publicador = FakePublicador({"marts/antigo.parquet", "manifesto.json"})
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
    publicador = FakePublicador({"marts/dim_uf.parquet"})
    with pytest.raises(ErroPublicacao, match="nenhum mart"):
        publicar(publicador, vazio, AGORA, "v")
    assert publicador.ordem == []
