from datetime import UTC, date, datetime, timedelta

from coletor.agenda import tarefas_pendentes
from coletor.competencias import Competencia
from coletor.manifesto import RecursoCompleto
from coletor.meta import HistoricoColetas, RegistroColeta, Sucesso
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


def _mensal(**competencia):
    regra = {"tipo": "mes", "inicio": 2024, **competencia}
    return RecursoCompleto(
        "cgu",
        recurso(
            id="contratos",
            publicacao="por_competencia",
            competencia=regra,
            cadencia={"corrente": "semanal", "anteriores": "mensal"},
        ),
    )


def test_tarefas_mensais_desde_o_inicio_ate_o_mes_corrente():
    tarefas = tarefas_pendentes([_mensal()], HistoricoColetas(), date(2024, 3, 10))
    assert [t.competencia.rotulo for t in tarefas] == ["2024-01", "2024-02", "2024-03"]


def test_serie_mensal_encerrada_nao_agenda_depois_do_fim():
    tarefas = tarefas_pendentes([_mensal(fim="2024-02")], HistoricoColetas(), date(2026, 10, 5))
    assert [t.competencia.rotulo for t in tarefas] == ["2024-01", "2024-02"]


def test_mes_corrente_e_anterior_usam_a_cadencia_corrente():
    historico = HistoricoColetas()
    for rotulo in ("2024-01", "2024-02", "2024-03"):
        registro = RegistroColeta.novo(
            "e", _mensal(), Competencia.de_rotulo(rotulo), datetime(2024, 3, 2, 12, tzinfo=UTC), "v"
        )
        historico.registrar(registro.finalizar("carregada", datetime(2024, 3, 2, 12, tzinfo=UTC)))
    tarefas = tarefas_pendentes([_mensal()], historico, date(2024, 3, 10))  # 8 dias depois
    assert [t.competencia.rotulo for t in tarefas] == ["2024-02", "2024-03"]  # semanal vencida


def test_limite_por_execucao_fica_com_as_competencias_mais_recentes():
    rc = _mensal()
    rc = RecursoCompleto(rc.orgao, rc.recurso.model_copy(update={"limite_por_execucao": 2}))
    tarefas = tarefas_pendentes([rc], HistoricoColetas(), date(2024, 5, 10))
    assert [t.competencia.rotulo for t in tarefas] == ["2024-05", "2024-04"]


def _diario(limite=None):
    regra = {"tipo": "dia", "inicio": 2026}
    r = recurso(
        id="contratos",
        publicacao="por_competencia",
        competencia=regra,
        cadencia={"corrente": "semanal", "anteriores": "anual"},
    ).model_copy(update={"limite_por_execucao": limite})
    return RecursoCompleto("pncp", r)


def test_dias_ate_ontem():
    tarefas = tarefas_pendentes([_diario()], HistoricoColetas(), date(2026, 1, 4))
    assert [t.competencia.rotulo for t in tarefas] == ["2026-01-01", "2026-01-02", "2026-01-03"]


def test_dias_mais_recentes_primeiro_com_limite():
    tarefas = tarefas_pendentes([_diario(limite=2)], HistoricoColetas(), date(2026, 3, 1))
    assert [t.competencia.rotulo for t in tarefas] == ["2026-02-28", "2026-02-27"]
