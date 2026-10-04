from datetime import UTC, date, datetime, timedelta

from coletor.agenda import tarefas_pendentes
from coletor.competencias import Competencia
from coletor.manifesto import RecursoCompleto
from coletor.meta import HistoricoColetas, Sucesso
from tests.amostras import recurso

HOJE = date(2026, 10, 3)


def _instante(dia: date) -> datetime:
    return datetime(dia.year, dia.month, dia.day, 11, 0, tzinfo=UTC)


def _ceap() -> RecursoCompleto:
    return RecursoCompleto(
        "camara",
        recurso(
            id="ceap",
            url="https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip",
            publicacao="por_competencia",
            competencia={"tipo": "ano", "inicio": 2024},
            cadencia={"corrente": "diaria", "anteriores": "semanal"},
        ),
    )


def _sucesso(dia: date, competencia: date | None = None, colunas=None, sha="h") -> Sucesso:
    return Sucesso(_instante(dia), sha, competencia, colunas)


def test_sem_historico_tudo_esta_vencido():
    cnep = RecursoCompleto("cgu", recurso())
    tarefas = tarefas_pendentes([cnep, _ceap()], HistoricoColetas(), HOJE)
    assert [(t.recurso.id, t.competencia) for t in tarefas] == [
        ("cgu.cnep", None),
        ("camara.ceap", Competencia.de_ano(2024)),
        ("camara.ceap", Competencia.de_ano(2025)),
        ("camara.ceap", Competencia.de_ano(2026)),
    ]


def test_cadencias_do_ano_corrente_e_dos_anteriores():
    historico = HistoricoColetas(
        {
            ("camara.ceap", "2024"): _sucesso(HOJE - timedelta(days=7)),
            ("camara.ceap", "2025"): _sucesso(HOJE - timedelta(days=6)),
            ("camara.ceap", "2026"): _sucesso(HOJE),
        }
    )
    tarefas = tarefas_pendentes([_ceap()], historico, HOJE)
    assert [t.competencia.rotulo for t in tarefas] == ["2024"]


def test_snapshot_diario_coletado_ontem_esta_vencido():
    cnep = RecursoCompleto("cgu", recurso())
    ontem = HistoricoColetas({("cgu.cnep", "2026-10-01"): _sucesso(HOJE - timedelta(days=1))})
    hoje = HistoricoColetas({("cgu.cnep", "2026-10-02"): _sucesso(HOJE)})
    assert len(tarefas_pendentes([cnep], ontem, HOJE)) == 1
    assert tarefas_pendentes([cnep], hoje, HOJE) == []


def test_snapshot_por_data_de_coleta_recebe_a_competencia_de_hoje():
    deputados = RecursoCompleto(
        "camara",
        recurso(
            id="deputados",
            adaptador="api_json",
            url="https://x",
            competencia={"tipo": "data_coleta"},
            formato={"tipo": "json"},
        ),
    )
    [tarefa] = tarefas_pendentes([deputados], HistoricoColetas(), HOJE)
    assert tarefa.competencia == Competencia.de_dia(HOJE)
