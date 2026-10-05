from datetime import UTC, date, datetime

import pytest

from coletor.armazenamento import caminho_de_uri, caminho_original
from coletor.lago import Particionamento


def test_caminho_do_original_tem_data_hora_e_hash():
    instante = datetime(2026, 10, 3, 10, 30, tzinfo=UTC)
    caminho = caminho_original(
        "dev/", "cgu", "ceis", "2026-10-02", instante, "abcdef0123456789", "zip"
    )
    assert (
        caminho == "dev/originais/cgu/ceis/competencia=2026-10-02/20261003T103000_abcdef012345.zip"
    )


def test_caminho_a_partir_da_uri():
    assert caminho_de_uri("gs://bucket/a/b.zip") == "a/b.zip"
    with pytest.raises(ValueError):
        caminho_de_uri("/a/b.zip")


def test_decorador_de_particao():
    assert Particionamento("DAY", 60).decorador(date(2026, 10, 2)) == "20261002"
    assert Particionamento("YEAR").decorador(date(2025, 1, 1)) == "2025"
