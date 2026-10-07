"""CLI `coletor`: coleta, pipeline diário, estado, publicação e reconstrução."""

from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import sys
import uuid
from collections.abc import Callable, Mapping
from datetime import date, datetime
from functools import partial
from pathlib import Path

from coletor.agenda import Tarefa, tarefa_snapshot, tarefas_pendentes
from coletor.coleta import Dependencias, recarregar
from coletor.competencias import Competencia, data_brasilia, meses
from coletor.config import Config, ErroConfig, carregar_config
from coletor.dbt import ResultadoDbt, ambiente_dbt, banco_do_target, gerar_linhagem, rodar_dbt
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
# modelos do site público: rodam no `coletor site`, fora do dbt build do pipeline, para que uma
# falha neles não impeça a publicação dos marts
SELECAO_SITE = ["path:models/site", "site_alerta_tipos"]


GRUPOS = ("diario", "receita", "tse")
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
    pipeline.add_argument("--selecao-tse", type=Path, help="JSON do vetor candidato explicito")

    estado = sub.add_parser("estado", help="sincroniza o lago local com o bucket privado")
    estado.add_argument("acao", choices=["restaurar", "salvar"])
    estado.add_argument(
        "--aditivo",
        action="store_true",
        help="salvar: só envia arquivos novos de raw/ e meta/ (nunca apaga nem sobrescreve)",
    )

    site = sub.add_parser("site", help="gera os arquivos do site público a partir do dbt")
    site.add_argument(
        "--esquemas", type=Path, default=Path("site/esquemas"), help="JSON Schemas do site"
    )

    publicar = sub.add_parser("publicar", help="gera linhagem e publica dados validados")
    publicar.add_argument("--execucao-tse", help="ID explicito do build C2 aprovado")

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
    dbt_com_coleta_falha: bool = True,
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
            if dbt_com_coleta_falha or (
                resumo.sucesso and resumo.adiadas == 0 and resumo.nao_publicadas == 0
            ):
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
    from coletor.tse.execucao import preparar_execucao_tse
    from coletor.tse.modelos import SelecaoTse
    from coletor.tse.pipeline import preparar_e_promover_tse

    recursos = _recursos(args, manifesto)
    selecao = None
    if args.selecao_tse:
        if any(rc.orgao != "tse" for rc in recursos) or args.grupo != "tse":
            raise ErroUso("--selecao-tse exige grupo tse e somente recursos TSE")
        try:
            selecao = SelecaoTse(**json.loads(args.selecao_tse.read_bytes()))
        except (OSError, TypeError, ValueError) as erro:
            raise ErroUso("JSON da selecao TSE invalido") from erro
    inicio = deps.agora()
    repo.publicar_fontes(manifesto, inicio)
    historico = repo.carregar_historico()
    tarefas = tarefas_pendentes(recursos, historico, data_brasilia(inicio))
    log.info("%d tarefa(s) pendente(s)", len(tarefas))

    def dbt() -> ResultadoDbt:
        from coletor.esquemas import carregar_esquemas, garantir_fontes

        criadas = garantir_fontes(deps.config.lago, carregar_esquemas(args.dbt_dir))
        if criadas:
            log.warning("fontes ainda sem dados (Parquet vazio criado): %s", ", ".join(criadas))
        execucao_id = str(uuid.uuid4())
        modo = "candidato" if selecao is not None else "privado-legado"
        print(f"execucao_tse={execucao_id} modo={modo}")
        if selecao is not None:
            recibo = preparar_e_promover_tse(
                deps.config.lago,
                selecao,
                execucao_id,
                args.target,
                partial(rodar_dbt_, args.dbt_dir),
            )
            print(f"execucao_tse={execucao_id} validacao=aprovada")
            return recibo.resultado
        preparada = preparar_execucao_tse(deps.config.lago, execucao_id, args.target)
        with ambiente_dbt(deps.config.lago, deps.config.publico):
            return rodar_dbt_(
                args.dbt_dir,
                args.target,
                deps.config.publico,
                [
                    "--exclude",
                    *SELECAO_SITE,
                    "--vars",
                    json.dumps(preparada.vars_dbt),
                    "--target-path",
                    (preparada.saida.parent / "dbt-target").as_posix(),
                ],
            )

    return _rodar_tarefas(
        tarefas, historico, deps, repo, inicio, False, dbt=dbt, dbt_com_coleta_falha=selecao is None
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
    from coletor.tse.execucao import preparar_execucao_tse
    from coletor.tse.publicacao import publicar_tse

    selecao = recibo = None
    if args.execucao_tse:
        preparada, selecao, recibo, variaveis = _publicacao_tse_preparada(
            deps.config.lago, args.execucao_tse, args.target
        )
    else:
        # Somente docs privados: nao afirma continuidade com build anterior nem envia C2.
        execucao = preparar_execucao_tse(deps.config.lago, str(uuid.uuid4()), args.target)
        preparada, variaveis = execucao.saida, execucao.vars_dbt
    argumentos = [
        "--vars",
        json.dumps(variaveis),
        "--target-path",
        (preparada.parent / "dbt-target").as_posix(),
    ]
    with ambiente_dbt(deps.config.lago, deps.config.publico):
        if not gerar_linhagem(
            args.dbt_dir, args.target, deps.config.publico, argumentos=argumentos
        ):
            log.error("dbt docs generate falhou: nada foi publicado")
            return 1
    publicador = R2Publicador(
        env["R2_CONTA"], env["R2_CHAVE_ID"], env["R2_SEGREDO"], env["R2_BUCKET"]
    )
    publicar(publicador, deps.config.publico, deps.agora(), deps.config.versao)
    if recibo is not None:
        publicar_tse(publicador, preparada, selecao, deps.agora(), deps.config.versao, recibo)
    return 0


def _site(args: argparse.Namespace, env: Mapping[str, str], rodar_dbt_: RodarDbt) -> int:
    """Roda os modelos do site no dbt e grava `ELEITORADO_PUBLICO/site`; não usa o GCP."""
    from coletor.site import ErroSite, gerar_site

    lago = Path(env.get("ELEITORADO_LAGO", "dados"))
    publico = Path(env.get("ELEITORADO_PUBLICO", "dados/publico"))
    from coletor.tse.execucao import preparar_execucao_tse

    preparada = preparar_execucao_tse(lago, str(uuid.uuid4()), args.target)
    argumentos = [
        "--select",
        *SELECAO_SITE,
        "--vars",
        json.dumps(preparada.vars_dbt, sort_keys=True),
        "--target-path",
        (preparada.saida.parent / "dbt-target").as_posix(),
    ]
    with ambiente_dbt(lago, publico):
        resultado = rodar_dbt_(args.dbt_dir, args.target, publico, argumentos)
    if resultado.status != "sucesso":
        log.error("dbt dos modelos do site falhou: %s", resultado)
        return 1
    try:
        quantidade = gerar_site(banco_do_target(lago, args.target), publico, args.esquemas)
    except ErroSite as erro:
        log.error("site não gerado: %s", erro)
        return 1
    log.info("site: %d arquivo(s) em %s", quantidade, publico / "site")
    return 0


def _publicacao_tse_preparada(lago: Path, execucao_id: str, target: str):
    from coletor.tse.modelos import ReciboValidacaoTse, SelecaoTse
    from coletor.tse.selecao import conferir_recibo_tse

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", execucao_id):
        raise ErroUso("ID de execucao TSE invalido")
    lago = lago.resolve()
    pasta = lago / "estado/tse/publicacoes/preparadas" / execucao_id
    try:
        prep = json.loads((pasta / "preparacao.json").read_bytes())
        if (
            prep["execucao_id"] != execucao_id
            or prep["target"] != target
            or prep["vars"]["tse_saida"] != (pasta / "marts").as_posix()
        ):
            raise ValueError("preparacao de outra execucao/target/saida")
        selecao = SelecaoTse(**prep["selecao"])
        dados = json.loads((pasta / "recibo.json").read_bytes())["recibo"]
        recibo = ReciboValidacaoTse(**{**dados, "resultado": ResultadoDbt(**dados["resultado"])})
        if recibo.execucao_id != execucao_id:
            raise ValueError("recibo de outra execucao")
        conferir_recibo_tse(lago, selecao, recibo)
    except (OSError, TypeError, KeyError, ValueError) as erro:
        raise ErroUso("execucao TSE nao possui evidencia publicavel") from erro
    return pasta / "marts", selecao, recibo, prep["vars"]


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
    from coletor.tse.execucao import preparar_execucao_tse

    preparada = preparar_execucao_tse(config.lago, execucao_id, args.target)
    with ambiente_dbt(config.lago, config.publico):
        resultado = rodar_dbt_(
            args.dbt_dir,
            args.target,
            config.publico,
            [
                "--full-refresh",
                "--vars",
                json.dumps({**preparada.vars_dbt, "fonte_historico": "replay"}),
                "--select",
                *SELECAO_HISTORICOS,
            ],
        )
    if resultado.status != "sucesso":
        log.error("dbt da reconstrução falhou: %s", resultado)
        return 1
    # as views de staging ficaram apontando para o replay: volta a apontá-las para o raw
    with ambiente_dbt(config.lago, config.publico):
        resultado = rodar_dbt_(
            args.dbt_dir,
            args.target,
            config.publico,
            ["--select", "staging", "--vars", json.dumps(preparada.vars_dbt)],
        )
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
    if args.comando == "site":
        return _site(args, env, dbt or rodar_dbt)
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
