"""CLI do agente investigador: `uv run agente <comando>`."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from agente.config import ConfigAgente, carregar

log = logging.getLogger("agente")

SAIDA_PAUSADA = 3
SAIDA_TRAVA = 4
SAIDA_PREPARO = 5


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agente", description="Agente investigador L1")
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("preparar", help="sincroniza o lago de produção e roda o dbt local")
    investigar = sub.add_parser("investigar", help="investigação livre, com tema ou retomada")
    investigar.add_argument("--tema", help="foco da investigação (sem tema: livre)")
    investigar.add_argument("--retomar", help="id de uma investigação pausada")
    relatorio = sub.add_parser("relatorio", help="refaz o relatório HTML de uma investigação")
    relatorio.add_argument("id")
    sub.add_parser("indice", help="refaz investigacoes/index.html")
    caderno = sub.add_parser("caderno", help="lista os casos do caderno")
    caderno.add_argument(
        "--situacao", choices=["aberto", "inconclusivo", "confirmado", "descartado"]
    )
    sub.add_parser("avaliar", help="roda o agente sobre casos plantados (consome a assinatura)")
    return parser


def _controlador(config: ConfigAgente, arquivo_config: Path | None = None):
    from agente.controlador import Controlador, Dependencias
    from agente.executor import ExecutorClaude
    from agente.preparar import preparar

    executor = ExecutorClaude(config.raiz, config.modelo, arquivo_config=arquivo_config)
    return Controlador(Dependencias(config, executor, lambda: preparar(config, os.environ)))


def _resumir(config: ConfigAgente, estado) -> None:
    confirmados = sum(r.situacao == "confirmado" for r in estado.achados)
    relatorio = config.investigacoes / estado.id / "relatorio.html"
    resumo = {
        "id": estado.id,
        "situacao": estado.situacao,
        "achados": confirmados,
        "motivo": estado.motivo_parada,
        "relatorio": str(relatorio) if relatorio.exists() else None,
    }
    (config.investigacoes / "ultima.json").write_text(
        json.dumps(resumo, ensure_ascii=False), encoding="utf-8"
    )
    print(f"{estado.id}: {estado.situacao}, {confirmados} achado(s) confirmado(s)")
    if estado.motivo_parada:
        print(f"motivo: {estado.motivo_parada}")
    if resumo["relatorio"]:
        print(f"relatório: {resumo['relatorio']}")


def _investigar(args: argparse.Namespace, config: ConfigAgente) -> int:
    from agente.controlador import ErroTrava, trava
    from agente.preparar import ErroPreparo

    controlador = _controlador(config)
    try:
        with trava(config.investigacoes, datetime.now(UTC)):
            if args.retomar:
                pasta = config.investigacoes / args.retomar
            elif not args.tema and (pendente := controlador.pendente()):
                log.info("retomando a investigação %s", pendente.name)
                pasta = pendente
            else:
                pasta = controlador.nova(args.tema)
            estado = controlador.executar(pasta)
    except ErroTrava as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return SAIDA_TRAVA
    except ErroPreparo as erro:
        print(f"erro ao preparar os dados: {erro}", file=sys.stderr)
        return SAIDA_PREPARO
    _resumir(config, estado)
    return SAIDA_PAUSADA if estado.situacao == "pausada" else 0


def _avaliar(config: ConfigAgente) -> int:
    from agente.avaliacao import contexto_de_avaliacao, preparar_avaliacao, verificar
    from agente.preparar import Preparo, gerar_contexto

    arquivo = preparar_avaliacao(config.raiz, config.modelo)
    avaliacao = carregar(arquivo, config.raiz)
    avaliacao.investigacoes.mkdir(parents=True, exist_ok=True)
    contexto = contexto_de_avaliacao(gerar_contexto(avaliacao))
    (avaliacao.investigacoes / "contexto.md").write_text(contexto, encoding="utf-8")
    controlador = _controlador(avaliacao, arquivo)
    controlador.deps.preparar = lambda: Preparo({"lago": "avaliação"}, False, [])
    estado = controlador.executar(controlador.nova(None))
    _resumir(avaliacao, estado)
    resultado = verificar(estado)
    for criterio, passou in resultado.items():
        print(f"{'ok ' if passou else 'FALHOU'} {criterio}")
    return 0 if all(resultado.values()) else 1


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = carregar()
    if args.comando == "preparar":
        from agente.preparar import preparar

        preparo = preparar(config, os.environ)
        print(f"dados: {preparo.versao_dados}; casos a revisar: {len(preparo.revisar)}")
        return 0
    if args.comando == "investigar":
        return _investigar(args, config)
    if args.comando == "relatorio":
        from agente import estado as persistencia
        from agente.relatorio import gerar, gerar_indice

        pasta = config.investigacoes / args.id
        print(gerar(persistencia.carregar(pasta), pasta, datetime.now(UTC)))
        gerar_indice(config.investigacoes)
        return 0
    if args.comando == "indice":
        from agente.relatorio import gerar_indice

        print(gerar_indice(config.investigacoes))
        return 0
    if args.comando == "caderno":
        from agente.caderno import Caderno

        for caso in Caderno(config.caderno).listar(args.situacao):
            print(f"[{caso.caso_id}] {caso.situacao:12} {caso.titulo}")
        return 0
    return _avaliar(config)


if __name__ == "__main__":
    sys.exit(main())
