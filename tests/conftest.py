from __future__ import annotations

import pytest

from coletor.http import ClienteHttp


@pytest.fixture
def http() -> ClienteHttp:
    cliente = ClienteHttp(dormir=lambda segundos: None)
    yield cliente
    cliente.fechar()
