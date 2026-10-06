import importlib.util
import sys
from pathlib import Path

ARQUIVO = Path(__file__).resolve().parent.parent / "scripts" / "virada.py"
especificacao = importlib.util.spec_from_file_location("virada", ARQUIVO)
virada = importlib.util.module_from_spec(especificacao)
sys.modules["virada"] = virada  # o dataclass precisa do módulo registrado
especificacao.loader.exec_module(virada)


def test_planeja_so_as_pastas_do_lago_e_sem_sobrescrever():
    objetos = {
        "paralelo/originais/cgu/ceis/a.zip": 10,
        "paralelo/raw/cgu/ceis/2026/x.parquet": 5,
        "paralelo/meta/coletas/2026/c.parquet": 2,
        "paralelo/estado/historicos/h.parquet": 3,
        "paralelo/carga/temp.parquet": 1,  # fora das pastas: não vai
        "originais/cgu/ceis/antigo.zip": 7,  # do pipeline antigo: fica
        "raw/cgu/ceis/2026/x.parquet": 5,  # já existe igual: não copia
        "paralelo/meta/coletas/2026/d.parquet": 4,
        "meta/coletas/2026/d.parquet": 9,  # mesmo nome, outro tamanho: divergente
    }
    plano = virada.planejar(objetos)
    assert plano.copiar == [
        ("paralelo/estado/historicos/h.parquet", "estado/historicos/h.parquet"),
        ("paralelo/meta/coletas/2026/c.parquet", "meta/coletas/2026/c.parquet"),
        ("paralelo/originais/cgu/ceis/a.zip", "originais/cgu/ceis/a.zip"),
    ]
    assert plano.ja_existem == ["raw/cgu/ceis/2026/x.parquet"]
    assert plano.divergentes == ["meta/coletas/2026/d.parquet"]


def test_conferencia_da_copia():
    copiado = {"paralelo/raw/a.parquet": 5, "raw/a.parquet": 5}
    assert virada.conferir_copia(copiado) == []
    assert virada.conferir_copia({"paralelo/raw/a.parquet": 5}) == ["paralelo/raw/a.parquet"]
    assert virada.conferir_copia({"paralelo/raw/a.parquet": 5, "raw/a.parquet": 4}) == [
        "raw/a.parquet"
    ]


class _Blob:
    def __init__(self, bucket, nome):
        self.bucket, self.nome = bucket, nome

    def rewrite(self, fonte, token=None, if_generation_match=None):
        assert if_generation_match == 0  # nunca sobrescreve
        self.bucket.chamadas.append((fonte.nome, self.nome, token))
        if token is None and fonte.nome.endswith("grande.zip"):
            return "continua", 1, 2  # objeto grande: precisa de outra chamada
        self.bucket.objetos[self.nome] = self.bucket.objetos[fonte.nome]
        return None, 2, 2


class _Bucket:
    def __init__(self, objetos):
        self.objetos = dict(objetos)
        self.chamadas = []

    def blob(self, nome):
        return _Blob(self, nome)


def test_copia_objeto_grande_em_varias_chamadas():
    bucket = _Bucket({"paralelo/originais/grande.zip": 9})
    virada._copiar(bucket, "paralelo/originais/grande.zip", "originais/grande.zip")
    assert bucket.chamadas == [
        ("paralelo/originais/grande.zip", "originais/grande.zip", None),
        ("paralelo/originais/grande.zip", "originais/grande.zip", "continua"),
    ]
    assert bucket.objetos["originais/grande.zip"] == 9
