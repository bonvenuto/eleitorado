"""CLI `coletor`: coleta, pipeline diário, estado, publicação e reconstrução."""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
import uuid
from collections.abc import Callable, Mapping
from datetime import date, datetime
from pathlib import Path

from coletor.agenda import Tarefa, tarefa_snapshot, tarefas_pendentes
from coletor.coleta import Dependencias, recarregar
from coletor.competencias import Competencia, data_brasilia, meses
from coletor.config import Config, ErroConfig, carregar_config
from coletor.dbt import ResultadoDbt, banco_do_target, gerar_linhagem, rodar_dbt
from coletor.execucao import ResumoColetas, registro_execucao, rodar
from coletor.manifesto import ErroManifesto, Manifesto, carregar_manifesto
from coletor.meta import HistoricoColetas, RepositorioMeta

log = logging.getLogger("coletor")

Fabrica = Callable[[Config], Dependencias]
RodarDbt = Callable[..., ResultadoDbt]

# Saída do `pipeline` quando só coletas falharam e o dbt passou: os marts podem ser publicados (o
# workflow publica com 0 ou 3), mas o job termina vermelho para a falha ficar visível.
SAIDA_SO_COLETAS_FALHARAM = 3

# recursos cujos snapshots alimentam os históricos (fonte_snapshot no dbt)
RECURSOS_HISTORICO = ("cgu.ceis", "cgu.cnep", "camara.deputados", "senado.senadores")
SELECAO_HISTORICOS = ["+int_cgu__sancoes_eventos+", "+int_parlamentares__eventos+"]


GRUPOS = ("diario", "receita")
AJUDA_GRUPO = "grupo de recursos quando --recursos não é dado (padrão: diario)"


class ErroUso(Exception):
    """Uso incorreto da CLI; sai com código 2."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="coletor", description="Coletor de dados públicos")
    parser.add_argument(
        "--fontes", type=Path, default=Path("fontes"), help="diretório do manifesto"
    )
    parser.add_argument("--dbt-dir", type=Path, default=Path("dbt"), help="projeto dbt")
    parser.add_argument("--target", default="prod", help="target do dbt")
    sub = parser.add_subparsers(dest="comando", required=True)

    sub.add_parser("fontes", help="lista os recursos e a última coleta bem-sucedida")

    executar = sub.add_parser("executar", help="coleta o que está com o prazo vencido")
    executar.add_argument("--recursos", help="ids separados por vírgula (padrão: todos)")
    executar.add_argument("--forcar", action="store_true", help="ignora a deduplicação por hash")
    executar.add_argument("--grupo", choices=GRUPOS, default="diario", help=AJUDA_GRUPO)

    coletar = sub.add_parser("coletar", help="coleta manual e backfill de um recurso")
    coletar.add_argument("recurso")
    grupo = coletar.add_mutually_exclusive_group()
    grupo.add_argument("--competencia", help="ano (AAAA) ou mês (AAAA-MM)")
    grupo.add_argument("--de", type=int, help="primeiro ano do intervalo")
    coletar.add_argument("--ate", type=int, help="último ano do intervalo (padrão: ano atual)")
    coletar.add_argument("--forcar", action="store_true")

    pipeline = sub.add_parser("pipeline", help="coleta o que está vencido e roda o dbt build")
    pipeline.add_argument("--recursos", help="ids separados por vírgula (padrão: todos)")
    pipeline.add_argument("--grupo", choices=GRUPOS, default="diario", help=AJUDA_GRUPO)

    estado = sub.add_parser("estado", help="sincroniza o lago local com o bucket privado")
    estado.add_argument("acao", choices=["restaurar", "salvar"])
    estado.add_argument(
        "--aditivo",
        action="store_true",
        help="salvar: só envia arquivos novos de raw/ e meta/ (nunca apaga nem sobrescreve)",
    )

    sub.add_parser("publicar", help="gera a linhagem e envia marts e linhagem ao bucket público")

    reconstruir = sub.add_parser(
        "reconstruir", help="refaz os históricos a partir dos originais no bucket"
    )
    reconstruir.add_argument(
        "--origem-prefixo",
        help="prefixo dos originais (padrão: o do ambiente; '' para a raiz do bucket)",
    )

    return parser


def _rodar_tarefas(
    tarefas: list[Tarefa],
    historico: HistoricoColetas,
    deps: Dependencias,
    repo: RepositorioMeta,
    inicio: datetime,
    forcar: bool,
    dbt: Callable[[], ResultadoDbt] | None = None,
) -> int:
    """Roda as coletas e, se pedido, o dbt; a execução é sempre registrada."""
    execucao_id = str(uuid.uuid4())
    resumo = ResumoColetas()
    resultado_dbt: ResultadoDbt | None = None
    try:
        resumo = rodar(tarefas, historico, deps, repo, execucao_id, forcar)
    except Exception:
        log.exception("coletas interrompidas")
        resumo.contar("falha")
    try:
        if dbt is not None:
            resultado_dbt = ResultadoDbt("falha", None)
            resultado_dbt = dbt()
    except Exception:
        log.exception("dbt interrompido")
    finally:
        repo.registrar_execucao(
            registro_execucao(execucao_id, deps.config.origem, deps, inicio, resumo, resultado_dbt)
        )
    log.info("resumo: %s dbt: %s", resumo, resultado_dbt)
    dbt_ok = resultado_dbt is None or resultado_dbt.status == "sucesso"
    if resumo.sucesso and dbt_ok:
        return 0
    if dbt is not None and dbt_ok:
        return SAIDA_SO_COLETAS_FALHARAM
    return 1


def _fontes(manifesto: Manifesto, repo: RepositorioMeta) -> int:
    historico = repo.carregar_historico()
    for rc in manifesto.todos():
        ultima = historico.ultima_data_sucesso(rc.id)
        regra = rc.recurso
        print(f"{rc.id:20} {regra.publicacao:16} {regra.cadencia.corrente:8} {ultima or '-'}")
    return 0


def _recursos(args: argparse.Namespace, manifesto: Manifesto) -> list:
    if args.recursos:
        return [manifesto.obter(item.strip()) for item in args.recursos.split(",")]
    return [rc for rc in manifesto.todos() if rc.recurso.grupo == args.grupo]


def _executar(
    args: argparse.Namespace, manifesto: Manifesto, deps: Dependencias, repo: RepositorioMeta
) -> int:
    inicio = deps.agora()
    repo.publicar_fontes(manifesto, inicio)
    historico = repo.carregar_historico()
    tarefas = tarefas_pendentes(_recursos(args, manifesto), historico, data_brasilia(inicio))
    log.info("%d tarefa(s) pendente(s)", len(tarefas))
    return _rodar_tarefas(tarefas, historico, deps, repo, inicio, args.forcar)


def _pipeline(
    args: argparse.Namespace,
    manifesto: Manifesto,
    deps: Dependencias,
    repo: RepositorioMeta,
    rodar_dbt_: RodarDbt,
) -> int:
    inicio = deps.agora()
    repo.publicar_fontes(manifesto, inicio)
    historico = repo.carregar_historico()
    tarefas = tarefas_pendentes(_recursos(args, manifesto), historico, data_brasilia(inicio))
    log.info("%d tarefa(s) pendente(s)", len(tarefas))

    def dbt() -> ResultadoDbt:
        from coletor.esquemas import carregar_esquemas, garantir_fontes

        criadas = garantir_fontes(deps.config.lago, carregar_esquemas(args.dbt_dir))
        if criadas:
            log.warning("fontes ainda sem dados (Parquet vazio criado): %s", ", ".join(criadas))
        return rodar_dbt_(args.dbt_dir, args.target, deps.config.publico)

    return _rodar_tarefas(
        tarefas,
        historico,
        deps,
        repo,
        inicio,
        False,
        dbt=dbt,
    )


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
        mensal = rc.recurso.competencia.tipo == "mes"
        esperado = {"ano": 4, "mes": 7, "dia": 10}.get(rc.recurso.competencia.tipo)
        if args.competencia:
            try:
                competencia = Competencia.de_rotulo(args.competencia)
            except ValueError:
                raise ErroUso(f"competência inválida: {args.competencia}") from None
            if esperado is not None and len(args.competencia) != esperado:
                raise ErroUso(
                    "--competencia deve ser AAAA (anual), AAAA-MM (mensal) ou AAAA-MM-DD (diária)"
                )
            alvos = [competencia]
        elif args.de is not None:
            anos_alvo = range(args.de, (args.ate or hoje.year) + 1)
            if mensal:
                fim = date(hoje.year, hoje.month, 1)
                if rc.recurso.competencia.fim:
                    fim = min(fim, Competencia.de_rotulo(rc.recurso.competencia.fim).data)
                alvos = [
                    Competencia.de_mes(d.year, d.month)
                    for d in meses(date(min(anos_alvo), 1, 1), fim)
                    if d.year in anos_alvo
                ]
            else:
                alvos = [Competencia.de_ano(ano) for ano in anos_alvo]
        else:
            raise ErroUso(f"{rc.id}: informe --competencia ou --de/--ate")
        tarefas = [Tarefa(rc, competencia) for competencia in alvos]
    historico = repo.carregar_historico()
    return _rodar_tarefas(tarefas, historico, deps, repo, inicio, args.forcar)


def _estado(args: argparse.Namespace, deps: Dependencias) -> int:
    from coletor import estado

    config = deps.config
    banco = banco_do_target(config.lago, args.target)
    if args.acao == "restaurar":
        estado.restaurar(deps.armazenamento, config.prefixo_gcs, config.lago, banco)
    else:
        estado.salvar(
            deps.armazenamento, config.prefixo_gcs, config.lago, banco, aditivo=args.aditivo
        )
    return 0


def _publicar(args: argparse.Namespace, deps: Dependencias, env: Mapping[str, str]) -> int:
    from coletor.publicacao import R2Publicador, publicar

    faltando = [
        nome for nome in ("R2_CONTA", "R2_CHAVE_ID", "R2_SEGREDO", "R2_BUCKET") if not env.get(nome)
    ]
    if faltando:
        raise ErroConfig(f"variáveis de ambiente ausentes: {', '.join(faltando)}")
    if not gerar_linhagem(args.dbt_dir, args.target, deps.config.publico):
        log.error("dbt docs generate falhou: nada foi publicado")
        return 1
    publicador = R2Publicador(
        env["R2_CONTA"], env["R2_CHAVE_ID"], env["R2_SEGREDO"], env["R2_BUCKET"]
    )
    publicar(publicador, deps.config.publico, deps.agora(), deps.config.versao)
    return 0


def _reconstruir(
    args: argparse.Namespace,
    manifesto: Manifesto,
    deps: Dependencias,
    repo: RepositorioMeta,
    rodar_dbt_: RodarDbt,
) -> int:
    """Recria no lago (`replay/`) os snapshots de todas as datas e refaz os históricos.

    Roda depois de um `pipeline` completo: os marts que dependem dos históricos (o alerta de
    fornecedor sancionado) também leem a cota, que precisa já existir no banco.
    """
    config = deps.config
    prefixo = config.prefixo_gcs if args.origem_prefixo is None else args.origem_prefixo
    replay = config.lago / "replay"
    if replay.exists():
        shutil.rmtree(replay)
    historico = repo.carregar_historico()
    execucao_id = str(uuid.uuid4())
    falhas = 0
    for recurso_id in RECURSOS_HISTORICO:
        rc = manifesto.obter(recurso_id)
        base = f"{prefixo}originais/{rc.orgao}/{rc.recurso.id}/"
        ultimos: dict[str, str] = {}
        for caminho in deps.armazenamento.listar(base):  # ordem por nome = ordem no tempo
            rotulo = caminho.removeprefix(base).split("/", 1)[0].removeprefix("competencia=")
            ultimos[rotulo] = caminho
        log.info("%s: %d data(s) de referência", recurso_id, len(ultimos))
        for rotulo, caminho in sorted(ultimos.items()):
            registro = recarregar(
                rc,
                Competencia.de_rotulo(rotulo),
                f"gs://{config.bucket}/{caminho}",
                historico,
                deps,
                execucao_id,
                "replay",
            )
            repo.registrar_coleta(registro)
            if registro.status != "recarregada":
                falhas += 1
                log.error("%s %s: %s", recurso_id, rotulo, registro.erro)
    if falhas:
        log.error("%d original(is) com falha: os históricos não foram refeitos", falhas)
        return 1
    resultado = rodar_dbt_(
        args.dbt_dir,
        args.target,
        config.publico,
        [
            "--full-refresh",
            "--vars",
            "{fonte_historico: replay}",
            "--select",
            *SELECAO_HISTORICOS,
        ],
    )
    if resultado.status != "sucesso":
        log.error("dbt da reconstrução falhou: %s", resultado)
        return 1
    # as views de staging ficaram apontando para o replay: volta a apontá-las para o raw
    resultado = rodar_dbt_(args.dbt_dir, args.target, config.publico, ["--select", "staging"])
    shutil.rmtree(replay)
    return 0 if resultado.status == "sucesso" else 1


def main(
    argv: list[str] | None = None,
    fabrica: Fabrica | None = None,
    env: Mapping[str, str] | None = None,
    dbt: RodarDbt | None = None,
) -> int:
    import os

    args = _parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    env = os.environ if env is None else env
    deps: Dependencias | None = None
    try:
        config = carregar_config(env)
        log.info("ambiente=%s prefixo=%r lago=%s", config.ambiente, config.prefixo_gcs, config.lago)
        manifesto = carregar_manifesto(args.fontes)
        if fabrica is None:
            from coletor.gcp import montar_dependencias

            fabrica = montar_dependencias
        deps = fabrica(config)
        if args.comando == "estado":
            return _estado(args, deps)
        if args.comando == "publicar":
            return _publicar(args, deps, env)
        repo = RepositorioMeta(deps.warehouse)
        repo.preparar()
        if args.comando == "pipeline":
            return _pipeline(args, manifesto, deps, repo, dbt or rodar_dbt)
        if args.comando == "reconstruir":
            return _reconstruir(args, manifesto, deps, repo, dbt or rodar_dbt)
        if args.comando == "fontes":
            return _fontes(manifesto, repo)
        if args.comando == "executar":
            return _executar(args, manifesto, deps, repo)
        return _coletar(args, manifesto, deps, repo)
    except (ErroConfig, ErroManifesto, ErroUso) as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 2
    finally:
        if deps is not None:
            deps.http.fechar()


if __name__ == "__main__":
    raise SystemExit(main())
