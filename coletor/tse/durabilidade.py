"""Documentos privados completos e sincronizados antes da instalação exclusiva."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from coletor.adaptadores.base import ErroColeta
from coletor.hashes import json_canonico, sha256_arquivo


def sincronizar_pasta(pasta: Path) -> None:
    """Persiste entradas de diretório em POSIX; Windows usa arquivos fsync antes dos links."""
    if os.name != "nt":
        descritor = os.open(pasta, os.O_RDONLY)
        try:
            os.fsync(descritor)
        finally:
            os.close(descritor)


def gravar_json(destino: Path, dados: dict[str, Any], *, checksum: bool = False) -> None:
    """Instala documento por link exclusivo, sem expor JSON parcial ou sobrescrever."""
    conteudo = json_canonico(dados).encode("utf-8")
    if checksum:
        conteudo = json_canonico(
            {"sha256": hashlib.sha256(conteudo).hexdigest(), "dados": dados}
        ).encode("utf-8")
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = None
    try:
        with tempfile.NamedTemporaryFile(dir=destino.parent, delete=False) as saida:
            temporario = Path(saida.name)
            saida.write(conteudo)
            saida.flush()
            os.fsync(saida.fileno())
        os.link(temporario, destino)
        sincronizar_pasta(destino.parent)
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)


def ler_json_conferido(caminho: Path) -> dict[str, Any]:
    envelope = json.loads(caminho.read_text(encoding="utf-8"))
    dados = envelope["dados"]
    if hashlib.sha256(json_canonico(dados).encode("utf-8")).hexdigest() != envelope["sha256"]:
        raise ErroColeta("integridade do documento durável TSE divergente")
    return dados


class ErroRecuperacaoTse(OSError):
    """Estado incerto exige inspeção explícita do journal privado antes de consumir TSE."""

    def __init__(self, area: Path, mensagem: str):
        self.area = area
        super().__init__(f"{mensagem}; recuperação TSE: {area}")


class ErroCompensacaoTse(ErroRecuperacaoTse):
    """A falha original não foi totalmente compensada; backups não foram descartados."""

    def __init__(self, area: Path, original: BaseException, erros: list[BaseException]):
        self.original = original
        self.erros = tuple(erros)
        super().__init__(area, "compensação incompleta; estado incerto e bloqueado")


def conferir_recuperacao(lago: Path) -> None:
    """Journal incompleto/corrompido bloqueia; conclusão confirmada é apenas histórica."""
    for area in (lago / "estado/tse").glob(".recuperacao-*"):
        try:
            if (area / "compensacao.json").exists():
                raise ValueError("compensação pendente")
            plano = ler_json_conferido(area / "plano.json")
            concluida = ler_json_conferido(area / "concluida.json")
            confirmada = ler_json_conferido(area / "confirmada.json")
            if (
                plano.get("protocolo") != "tse:instalacao:v1"
                or concluida != confirmada
                or concluida.get("protocolo") != "tse:instalacao-concluida:v1"
                or concluida.get("plano_sha256") != sha256_arquivo(area / "plano.json")
            ):
                raise ValueError("conclusão sem plano íntegro correspondente")
        except (OSError, ValueError, KeyError, TypeError, ErroColeta) as erro:
            raise ErroRecuperacaoTse(area, "journal incompleto ou incerto") from erro


def _copiar_duravel(origem: Path, destino: Path) -> None:
    with origem.open("rb") as entrada, destino.open("xb") as saida:
        shutil.copyfileobj(entrada, saida)
        saida.flush()
        os.fsync(saida.fileno())


def _temporario_irmao(origem: Path, destino: Path, prefixo: str, temporarios: list[Path]) -> Path:
    with tempfile.NamedTemporaryFile(dir=destino.parent, prefix=prefixo, delete=False) as saida:
        caminho = Path(saida.name)
        temporarios.append(caminho)
        with origem.open("rb") as entrada:
            shutil.copyfileobj(entrada, saida)
        saida.flush()
        os.fsync(saida.fileno())
    return caminho


def instalar_com_compensacao(lago: Path, arquivos: list[tuple[Path, Path]]) -> None:
    """Instala em série; compensa falhas, ou conserva evidência e bloqueia estado incerto.

    Requer controlador serializado. Backups/stages nunca editam o inode anterior.
    Confirmada só nasce depois de concluir fsync; sua perda física bloqueia conservadoramente.
    """
    conferir_recuperacao(lago)
    if not arquivos:
        return
    estado = lago / "estado/tse"
    estado.mkdir(parents=True, exist_ok=True)
    area = Path(tempfile.mkdtemp(prefix=".recuperacao-", dir=estado))
    (area / "anteriores").mkdir()
    entradas = []
    instalados = []
    pastas_criadas = []
    temporarios = []
    try:
        for indice, (origem, destino) in enumerate(arquivos):
            if not destino.resolve().is_relative_to(lago.resolve()):
                raise ValueError("destino de instalação fora do lago")
            faltantes = []
            pasta = destino.parent
            while not pasta.exists():
                faltantes.append(pasta)
                pasta = pasta.parent
            for pasta in reversed(faltantes):
                pasta.mkdir()
                pastas_criadas.append(pasta)
            novo = _temporario_irmao(origem, destino, ".instalacao-", temporarios)
            backup = None
            if destino.exists():
                backup = area / "anteriores" / str(indice)
                _copiar_duravel(destino, backup)
            entradas.append(
                {
                    "destino": destino.relative_to(lago).as_posix(),
                    "novo": novo.relative_to(lago).as_posix(),
                    "sha256_novo": sha256_arquivo(novo),
                    "existia": backup is not None,
                    "backup": backup.relative_to(area).as_posix() if backup else None,
                    "sha256_anterior": sha256_arquivo(backup) if backup else None,
                }
            )
        gravar_json(
            area / "plano.json",
            {
                "protocolo": "tse:instalacao:v1",
                "entradas": entradas,
                "pastas_criadas": [p.relative_to(lago).as_posix() for p in pastas_criadas],
            },
            checksum=True,
        )
        sincronizar_pasta(area / "anteriores")
        sincronizar_pasta(estado)
        for entrada in entradas:
            destino = lago / entrada["destino"]
            instalados.append(entrada)  # inclui syscall que pode ter resultado incerto
            os.replace(lago / entrada["novo"], destino)
            sincronizar_pasta(destino.parent)
        gravar_json(
            area / "concluida.json",
            {
                "protocolo": "tse:instalacao-concluida:v1",
                "plano_sha256": sha256_arquivo(area / "plano.json"),
            },
            checksum=True,
        )
        # Nenhum fsync falível após a confirmação: só nasce após todos retornarem sucesso.
        # Se o link se perder numa queda física, o journal incompleto bloqueia por segurança.
        os.link(area / "concluida.json", area / "confirmada.json")
    except BaseException as original:
        erros = []
        if instalados:
            try:
                gravar_json(
                    area / "compensacao.json",
                    {
                        "protocolo": "tse:compensacao-pendente:v1",
                        "erro": str(original),
                    },
                    checksum=True,
                )
            except BaseException as erro:
                erros.append(erro)
        for entrada in reversed(instalados):
            destino = lago / entrada["destino"]
            try:
                if entrada["existia"]:
                    backup = area / entrada["backup"]
                    if sha256_arquivo(backup) != entrada["sha256_anterior"]:
                        raise ValueError("backup de compensação corrompido")
                    repor = _temporario_irmao(backup, destino, ".repor-", temporarios)
                    os.replace(repor, destino)
                elif destino.exists():
                    if sha256_arquivo(destino) != entrada["sha256_novo"]:
                        raise ValueError("destino novo divergente; não é seguro remover")
                    # Primeira inicialização é monotônica, mesmo se o vigente não foi instalado.
                    if destino != estado / "inicializado.json":
                        destino.unlink()
                sincronizar_pasta(destino.parent)
            except BaseException as erro:
                erros.append(erro)
        if not erros:
            try:
                for temporario in temporarios:
                    temporario.unlink(missing_ok=True)
                for pasta in reversed(pastas_criadas):
                    if pasta.exists() and not any(pasta.iterdir()):
                        pasta.rmdir()
                # Marcador novo já persistido não pode ser removido para reabrir bootstrap.
                if (estado / "inicializado.json").exists() and not (
                    estado / "vigente.json"
                ).exists():
                    raise ValueError(
                        "inicialização interrompida sem vigente; recuperação explícita"
                    )
                _retirar_journal(area)
            except BaseException as erro:
                erros.append(erro)
        if erros:
            raise ErroCompensacaoTse(area, original, erros) from original
        raise
    # Commit comprovado: retirar o journal inteiro antes de qualquer exclusão de conteúdo.
    # Uma falha de limpeza mantém estado concluído, nunca dispara compensação posterior.
    try:
        _retirar_journal(area)
    except OSError:
        logging.getLogger(__name__).warning("instalação TSE concluída; limpeza pendente: %s", area)


def _retirar_journal(area: Path) -> None:
    limpeza = area.with_name(area.name.replace(".recuperacao-", ".limpeza-", 1))
    os.rename(area, limpeza)
    try:
        shutil.rmtree(limpeza)
    except OSError:
        logging.getLogger(__name__).warning("journal TSE retirado; limpeza pendente: %s", limpeza)


@contextmanager
def pasta_temporaria(prefixo: str, pasta: Path | None = None):
    """Limpeza própria é não crítica: nunca mascara o resultado/erro da operação."""
    caminho = Path(tempfile.mkdtemp(prefix=prefixo, dir=pasta))
    try:
        yield caminho
    finally:
        try:
            shutil.rmtree(caminho)
        except OSError:
            logging.getLogger(__name__).warning("limpeza temporária TSE pendente: %s", caminho)
