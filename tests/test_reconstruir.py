"""`coletor reconstruir` (históricos a partir dos originais) e os comandos de estado."""

from dataclasses import replace
from datetime import date

import httpx
import pytest

from coletor.cli import main
from coletor.coleta import Dependencias
from coletor.dbt import ResultadoDbt
from coletor.lago import LagoWarehouse
from tests.amostras import AGORA, CNEP_CSV, RAIZ, zip_com

ENV = {"ELEITORADO_PROJETO": "projeto-teste", "ELEITORADO_BUCKET": "bucket-teste"}


@pytest.fixture
def deps_lago(tmp_path, config, http, armazenamento) -> Dependencias:
    config = replace(config, lago=tmp_path / "lago", publico=tmp_path / "publico")
    return Dependencias(
        config=config,
        http=http,
        armazenamento=armazenamento,
        warehouse=LagoWarehouse(config.lago, hoje=date(2026, 10, 3)),
        agora=lambda: AGORA,
    )


def _original(armazenamento, tmp_path, caminho: str, conteudo: bytes) -> None:
    origem = tmp_path / "original.zip"
    origem.write_bytes(conteudo)
    armazenamento.enviar(origem, caminho)


def _cnep(dia: str) -> bytes:
    return zip_com({f"{dia}_CNEP.csv": CNEP_CSV.encode("cp1252")})


class DbtFalso:
    def __init__(self, lago, status: str = "sucesso") -> None:
        self.lago = lago
        self.status = status
        self.chamadas: list[list[str]] = []
        self.datas_no_replay: list[str] = []

    def __call__(self, diretorio, target, publico, argumentos=()):
        self.chamadas.append(list(argumentos))
        pasta = self.lago / "replay" / "raw" / "cgu" / "cnep"
        if pasta.exists() and not self.datas_no_replay:
            self.datas_no_replay = sorted(p.name for p in pasta.iterdir())
        return ResultadoDbt(self.status, 0)


def _rodar(argumentos, deps, dbt=None) -> int:
    return main(
        ["--fontes", str(RAIZ / "fontes"), *argumentos],
        fabrica=lambda config: deps,
        env=ENV,
        dbt=dbt,
    )


def test_reconstruir_usa_o_ultimo_original_de_cada_data_e_refaz_os_historicos(
    deps_lago, armazenamento, tmp_path
):
    base = "dev/originais/cgu/cnep/"
    _original(
        armazenamento,
        tmp_path,
        f"{base}competencia=2026-10-01/20261001T100000_a.zip",
        _cnep("20261001"),
    )
    _original(
        armazenamento,
        tmp_path,
        f"{base}competencia=2026-10-02/20261002T100000_b.zip",
        b"corrompido",
    )
    _original(
        armazenamento,
        tmp_path,
        f"{base}competencia=2026-10-02/20261002T200000_c.zip",
        _cnep("20261002"),
    )
    dbt = DbtFalso(deps_lago.config.lago)

    assert _rodar(["reconstruir"], deps_lago, dbt) == 0

    assert dbt.datas_no_replay == ["20261001", "20261002"]  # o original corrompido foi ignorado
    assert dbt.chamadas == [
        [
            "--full-refresh",
            "--vars",
            "{fonte_historico: replay}",
            "--select",
            "+int_cgu__sancoes_eventos+",
            "+int_parlamentares__eventos+",
        ],
        ["--select", "staging"],
    ]
    assert not (deps_lago.config.lago / "replay").exists()
    registros = deps_lago.warehouse.consultar(
        "select status, destino, competencia from coletas order by competencia"
    )
    assert [(r["status"], r["destino"], r["competencia"]) for r in registros] == [
        ("recarregada", "replay", "2026-10-01"),
        ("recarregada", "replay", "2026-10-02"),
    ]


def test_reconstruir_le_os_originais_de_outro_prefixo(deps_lago, armazenamento, tmp_path):
    # no paralelo, o pipeline novo (prefixo paralelo/) reconstrói a partir dos originais da raiz
    _original(
        armazenamento,
        tmp_path,
        "originais/cgu/cnep/competencia=2026-10-01/20261001T100000_a.zip",
        _cnep("20261001"),
    )
    dbt = DbtFalso(deps_lago.config.lago)
    assert _rodar(["reconstruir", "--origem-prefixo", ""], deps_lago, dbt) == 0
    assert dbt.datas_no_replay == ["20261001"]


def test_reconstruir_com_original_ilegivel_nao_roda_o_dbt(deps_lago, armazenamento, tmp_path):
    _original(
        armazenamento,
        tmp_path,
        "dev/originais/cgu/cnep/competencia=2026-10-01/20261001T100000_a.zip",
        b"corrompido",
    )
    dbt = DbtFalso(deps_lago.config.lago)
    assert _rodar(["reconstruir"], deps_lago, dbt) == 1
    assert dbt.chamadas == []


def test_reconstruir_com_dbt_falhando_termina_com_erro(deps_lago, armazenamento, tmp_path):
    _original(
        armazenamento,
        tmp_path,
        "dev/originais/cgu/cnep/competencia=2026-10-01/20261001T100000_a.zip",
        _cnep("20261001"),
    )
    dbt = DbtFalso(deps_lago.config.lago, status="falha")
    assert _rodar(["reconstruir"], deps_lago, dbt) == 1
    assert len(dbt.chamadas) == 1  # não segue para o staging


def test_estado_pela_cli_usa_o_prefixo_do_ambiente(deps_lago, armazenamento):
    arquivo = deps_lago.config.lago / "raw" / "cgu" / "cnep" / "20261002" / "c.parquet"
    arquivo.parent.mkdir(parents=True)
    arquivo.write_bytes(b"x")
    assert _rodar(["estado", "salvar"], deps_lago) == 0
    assert "dev/raw/cgu/cnep/20261002/c.parquet" in armazenamento.objetos
    arquivo.unlink()
    assert _rodar(["estado", "restaurar"], deps_lago) == 0
    assert arquivo.read_bytes() == b"x"


def test_publicar_sem_credenciais_do_r2_falha_antes_de_tudo(deps_lago, capsys):
    assert _rodar(["publicar"], deps_lago) == 2
    assert "R2_CONTA" in capsys.readouterr().err


def test_pipeline_cria_fontes_vazias_antes_do_dbt(deps_lago, respx_mock):
    vistos = []

    def dbt(diretorio, target, publico, argumentos=()):
        vistos.append((deps_lago.config.lago / "raw/cgu/licitacoes/vazio/vazio.parquet").exists())
        return ResultadoDbt("sucesso", 0)

    respx_mock.route().mock(return_value=httpx.Response(503))  # nenhuma fonte responde
    _rodar(["pipeline", "--recursos", "ibge.municipios"], deps_lago, dbt)
    assert vistos == [True]
