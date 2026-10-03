from __future__ import annotations

from pathlib import Path

import pytest

from coletor.config import Config
from coletor.http import ClienteHttp
from tests.fakes import FakeArmazenamento, FakeWarehouse


@pytest.fixture
def config() -> Config:
    return Config(
        projeto="projeto-teste",
        bucket="bucket-teste",
        regiao="southamerica-east1",
        ambiente="dev",
        versao="teste",
        origem="manual",
    )


@pytest.fixture
def armazenamento(tmp_path: Path) -> FakeArmazenamento:
    return FakeArmazenamento(tmp_path / "gcs")


@pytest.fixture
def warehouse(armazenamento: FakeArmazenamento) -> FakeWarehouse:
    return FakeWarehouse(armazenamento)


@pytest.fixture
def http() -> ClienteHttp:
    cliente = ClienteHttp(dormir=lambda segundos: None)
    yield cliente
    cliente.fechar()
