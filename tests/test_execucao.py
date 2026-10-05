from datetime import UTC, datetime

from coletor import execucao
from coletor.agenda import Tarefa
from coletor.competencias import Competencia
from coletor.manifesto import RecursoCompleto
from coletor.meta import HistoricoColetas, RegistroColeta
from tests.amostras import recurso

INSTANTE = datetime(2026, 1, 1, tzinfo=UTC)


class RepoFalso:
    def __init__(self):
        self.coletas = []

    def registrar_coleta(self, registro):
        self.coletas.append(registro)


def _tarefa(rid: str, url: str, pausa: float = 0) -> Tarefa:
    r = recurso(id=rid, url=url).model_copy(update={"pausa_segundos": pausa})
    return Tarefa(RecursoCompleto("cgu", r), Competencia.de_rotulo("2024-01"))


def test_bloqueio_adia_e_pula_o_resto_do_mesmo_servidor(monkeypatch, deps):
    chamadas = []
    pausas = []
    deps.dormir = pausas.append

    def coletar_falso(rc, competencia, historico, deps_, execucao_id, forcar):
        chamadas.append(rc.recurso.id)
        registro = RegistroColeta.novo(execucao_id, rc, competencia, INSTANTE, "v")
        if rc.recurso.id == "a":
            registro.http_status = 405
            registro.erro = "ErroHttp: 405"
            return registro.finalizar("adiada", INSTANTE)
        return registro.finalizar("carregada", INSTANTE)

    monkeypatch.setattr(execucao, "coletar", coletar_falso)
    tarefas = [
        _tarefa("a", "https://portal.exemplo/a/{anomes}", pausa=3),
        _tarefa("b", "https://portal.exemplo/b/{anomes}", pausa=3),  # mesmo servidor: pulada
        _tarefa("c", "https://outro.exemplo/c/{anomes}"),
    ]
    resumo = execucao.rodar(tarefas, HistoricoColetas(), deps, RepoFalso(), "e1")
    assert chamadas == ["a", "c"]
    assert (resumo.adiadas, resumo.carregadas, resumo.falhas) == (2, 1, 0)
    assert resumo.sucesso
    assert pausas == [3]
