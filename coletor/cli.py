"""CLI `coletor`: fontes, executar, coletar e recarregar."""

from __future__ import annotations

import argparse
import logging
import sys
import uuid
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path

from coletor.agenda import Tarefa, tarefa_snapshot, tarefas_pendentes
from coletor.coleta import EXPIRACAO_SNAPSHOT_DIAS, Dependencias, recarregar
from coletor.competencias import Competencia, data_brasilia
from coletor.config import Config, ErroConfig, carregar_config
from coletor.execucao import ResumoColetas, registro_execucao, rodar
from coletor.manifesto import ErroManifesto, Manifesto, carregar_manifesto
from coletor.meta import HistoricoColetas, RepositorioMeta

log = logging.getLogger("coletor")

Fabrica = Callable[[Config], Dependencias]


class ErroUso(Exception):
    """Uso incorreto da CLI; sai com código 2."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="coletor", description="Coletor de dados públicos")
    parser.add_argument(
        "--fontes", type=Path, default=Path("fontes"), help="diretório do manifesto"
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    sub.add_parser("fontes", help="lista os recursos e a última coleta bem-sucedida")

    executar = sub.add_parser("executar", help="coleta o que está com o prazo vencido")
    executar.add_argument("--recursos", help="ids separados por vírgula (padrão: todos)")
    executar.add_argument("--forcar", action="store_true", help="ignora a deduplicação por hash")

    coletar = sub.add_parser("coletar", help="coleta manual e backfill de um recurso")
    coletar.add_argument("recurso")
    grupo = coletar.add_mutually_exclusive_group()
    grupo.add_argument("--competencia", help="ano, para recursos por competência")
    grupo.add_argument("--de", type=int, help="primeiro ano do intervalo")
    coletar.add_argument("--ate", type=int, help="último ano do intervalo (padrão: ano atual)")
    coletar.add_argument("--forcar", action="store_true")

    recarga = sub.add_parser("recarregar", help="refaz a carga a partir do original no GCS")
    recarga.add_argument("recurso")
    recarga.add_argument("--competencia", required=True)
    recarga.add_argument("--coleta-id")
    recarga.add_argument("--destino", choices=["raw", "replay"], default="raw")
    return parser


def _rodar_tarefas(
    tarefas: list[Tarefa],
    historico: HistoricoColetas,
    deps: Dependencias,
    repo: RepositorioMeta,
    inicio: datetime,
    forcar: bool,
) -> int:
    execucao_id = str(uuid.uuid4())
    resumo = ResumoColetas()
    try:
        resumo = rodar(tarefas, historico, deps, repo, execucao_id, forcar)
    except Exception:
        log.exception("execução interrompida")
        resumo.contar("falha")
    finally:
        repo.registrar_execucao(
            registro_execucao(execucao_id, deps.config.origem, deps, inicio, resumo)
        )
    log.info("resumo: %s", resumo)
    return 0 if resumo.sucesso else 1


def _fontes(manifesto: Manifesto, repo: RepositorioMeta) -> int:
    historico = repo.carregar_historico()
    for rc in manifesto.todos():
        ultima = historico.ultima_data_sucesso(rc.id)
        regra = rc.recurso
        print(f"{rc.id:20} {regra.publicacao:16} {regra.cadencia.corrente:8} {ultima or '-'}")
    return 0


def _executar(
    args: argparse.Namespace, manifesto: Manifesto, deps: Dependencias, repo: RepositorioMeta
) -> int:
    if args.recursos:
        recursos = [manifesto.obter(item.strip()) for item in args.recursos.split(",")]
    else:
        recursos = manifesto.todos()
    inicio = deps.agora()
    repo.publicar_fontes(manifesto, inicio)
    historico = repo.carregar_historico()
    tarefas = tarefas_pendentes(recursos, historico, data_brasilia(inicio))
    log.info("%d tarefa(s) pendente(s)", len(tarefas))
    return _rodar_tarefas(tarefas, historico, deps, repo, inicio, args.forcar)


def _coletar(
    args: argparse.Namespace, manifesto: Manifesto, deps: Dependencias, repo: RepositorioMeta
) -> int:
    rc = manifesto.obter(args.recurso)
    inicio = deps.agora()
    hoje = data_brasilia(inicio)
    if rc.recurso.publicacao == "snapshot":
        if args.competencia or args.de is not None or args.ate is not None:
            raise ErroUso(f"{rc.id} é snapshot: não aceita --competencia, --de ou --ate")
        tarefas = [tarefa_snapshot(rc, hoje)]
    else:
        if args.ate is not None and args.de is None:
            raise ErroUso("--ate exige --de")
        if args.competencia:
            if not (len(args.competencia) == 4 and args.competencia.isdigit()):
                raise ErroUso("--competencia deve ser um ano, como 2025")
            anos_alvo = [int(args.competencia)]
        elif args.de is not None:
            anos_alvo = list(range(args.de, (args.ate or hoje.year) + 1))
        else:
            raise ErroUso(f"{rc.id}: informe --competencia ou --de/--ate")
        tarefas = [Tarefa(rc, Competencia.de_ano(ano)) for ano in anos_alvo]
    historico = repo.carregar_historico()
    return _rodar_tarefas(tarefas, historico, deps, repo, inicio, args.forcar)


def _recarregar(
    args: argparse.Namespace, manifesto: Manifesto, deps: Dependencias, repo: RepositorioMeta
) -> int:
    rc = manifesto.obter(args.recurso)
    try:
        competencia = Competencia.de_rotulo(args.competencia)
    except ValueError:
        raise ErroUso(f"competência inválida: {args.competencia}") from None
    hoje = data_brasilia(deps.agora())
    antiga = (hoje - competencia.data).days >= EXPIRACAO_SNAPSHOT_DIAS
    if args.destino == "raw" and rc.recurso.publicacao == "snapshot" and antiga:
        raise ErroUso(
            f"snapshot com {EXPIRACAO_SNAPSHOT_DIAS} dias ou mais expiraria no raw: "
            "use --destino replay"
        )
    if args.coleta_id:
        coleta = repo.buscar_coleta(args.coleta_id)
        if coleta is None:
            raise ErroUso(f"coleta {args.coleta_id} não encontrada")
        origem = (f"{coleta['orgao']}.{coleta['recurso']}", coleta["competencia"])
        if origem != (rc.id, competencia.rotulo):
            raise ErroUso(
                f"coleta {args.coleta_id} é de {origem[0]} competência {origem[1]}, "
                f"não de {rc.id} competência {competencia.rotulo}"
            )
        if not coleta["arquivo_original"]:
            raise ErroUso(f"coleta {args.coleta_id} ({coleta['status']}) está sem original no GCS")
        uri = coleta["arquivo_original"]
    else:
        prefixo = (
            f"{deps.config.prefixo_gcs}originais/{rc.orgao}/{rc.recurso.id}/"
            f"competencia={competencia.rotulo}/"
        )
        objetos = deps.armazenamento.listar(prefixo)
        if not objetos:
            raise ErroUso(f"nenhum original em gs://{deps.config.bucket}/{prefixo}")
        uri = f"gs://{deps.config.bucket}/{objetos[-1]}"
    historico = repo.carregar_historico()
    registro = recarregar(rc, competencia, uri, historico, deps, str(uuid.uuid4()), args.destino)
    repo.registrar_coleta(registro)
    log.info(
        "%s %s status=%s linhas=%s", rc.id, competencia.rotulo, registro.status, registro.linhas
    )
    if registro.erro:
        log.error(registro.erro)
    return 0 if registro.status == "recarregada" else 1


def main(
    argv: list[str] | None = None,
    fabrica: Fabrica | None = None,
    env: Mapping[str, str] | None = None,
) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    deps: Dependencias | None = None
    try:
        config = carregar_config(env)
        log.info("ambiente=%s projeto=%s", config.ambiente, config.projeto)
        manifesto = carregar_manifesto(args.fontes)
        if fabrica is None:
            from coletor.gcp import montar_dependencias

            fabrica = montar_dependencias
        deps = fabrica(config)
        repo = RepositorioMeta(deps.warehouse, config)
        repo.preparar()
        if args.comando == "fontes":
            return _fontes(manifesto, repo)
        if args.comando == "executar":
            return _executar(args, manifesto, deps, repo)
        if args.comando == "coletar":
            return _coletar(args, manifesto, deps, repo)
        return _recarregar(args, manifesto, deps, repo)
    except (ErroConfig, ErroManifesto, ErroUso) as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 2
    finally:
        if deps is not None:
            deps.http.fechar()


if __name__ == "__main__":
    raise SystemExit(main())
