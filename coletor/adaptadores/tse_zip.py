"""Um download TSE, múltiplas famílias consolidadas e validação até EOF/CRC."""

from __future__ import annotations

import csv
import zipfile
import zlib
from datetime import date
from pathlib import Path

from coletor.adaptadores import arquivo
from coletor.adaptadores.arquivo import LIMITE_DESCOMPACTADO
from coletor.adaptadores.base import ErroColeta, Extracao, preencher
from coletor.competencias import Competencia
from coletor.http import ClienteHttp
from coletor.manifesto import Recurso
from coletor.tse.layouts import LAYOUTS, PREFIXOS
from coletor.tse.modelos import FamiliaTse


def extrair(
    recurso: Recurso, competencia: Competencia | None, pasta: Path, http: ClienteHttp, hoje: date
) -> Extracao:
    """Reutiliza o download HTTP em fluxo; não baixa novamente para cada família."""
    _ano(competencia)
    return arquivo.extrair(recurso, competencia, pasta, http, hoje)


def _ano(competencia: Competencia | None) -> int:
    if competencia is None or competencia.rotulo != str(competencia.data.year):
        raise ErroColeta("TSE exige competência anual")
    ano = competencia.data.year
    if ano not in (2018, 2020, 2022, 2024):
        raise ErroColeta(f"TSE: ano sem layout aprovado: {ano}")
    return ano


def _validar_csv(caminho: Path, header: tuple[str, ...], membro: str) -> None:
    with caminho.open(encoding="latin-1", newline="") as entrada:
        leitor = csv.reader(entrada, delimiter=";", strict=True)
        encontrado = next(leitor, None)
        if encontrado != list(header) or len(set(encontrado)) != len(encontrado):
            raise ErroColeta(f"{membro}: cabeçalho inesperado para o layout aprovado")
        for linha in leitor:
            if linha == encontrado:
                raise ErroColeta(f"{membro}: cabeçalho repetido na linha {leitor.line_num}")
            if len(linha) != len(header):
                raise ErroColeta(f"{membro}: linha {leitor.line_num} truncada ou incompatível")


def preparar_familias(
    recurso: Recurso,
    competencia: Competencia,
    original: Path,
    pasta: Path,
    limite_membro_bytes: int = LIMITE_DESCOMPACTADO,
) -> tuple[FamiliaTse, ...]:
    """Extrai só membros exatos BRASIL, limitando cada um e verificando todo seu conteúdo.

    Resultados só são devolvidos após todas as famílias passarem. Em falha, remove somente
    os arquivos criados nesta chamada. Nenhum membro UF é lido ou somado ao consolidado.
    """
    ano = _ano(competencia)
    if not recurso.familias:
        raise ErroColeta("TSE exige famílias explícitas")
    if limite_membro_bytes <= 0:
        raise ErroColeta("teto por membro deve ser positivo")
    criados: list[Path] = []
    familias: list[FamiliaTse] = []
    try:
        with zipfile.ZipFile(original) as compactado:
            for familia, template in recurso.familias.items():
                if familia not in PREFIXOS:
                    raise ErroColeta(f"família TSE desconhecida: {familia}")
                nome = preencher(template, competencia, competencia.data)
                esperado = f"{PREFIXOS[familia]}_{ano}_BRASIL.csv"
                if nome != esperado:
                    raise ErroColeta(f"{familia}: membro deve ser exatamente {esperado}")
                membros = [
                    m for m in compactado.infolist() if m.filename == nome and not m.is_dir()
                ]
                if len(membros) != 1:
                    raise ErroColeta(f"{nome}: esperado um membro, encontrados {len(membros)}")
                membro = membros[0]
                if membro.file_size > limite_membro_bytes:
                    raise ErroColeta(f"{nome}: tamanho excede teto de {limite_membro_bytes} bytes")
                destino = pasta / f"tse_{familia}_{ano}.csv"
                # 'xb' protege arquivos anteriores de outra preparação ou tarefa.
                with destino.open("xb") as saida:
                    criados.append(destino)
                    with compactado.open(membro) as origem:
                        total = 0
                        while bloco := origem.read(1 << 20):
                            total += len(bloco)
                            if total > limite_membro_bytes:
                                raise ErroColeta(f"{nome}: conteúdo excede teto de bytes")
                            saida.write(bloco)
                        if total != membro.file_size:
                            raise ErroColeta(f"{nome}: tamanho descompactado divergente")
                _validar_csv(destino, LAYOUTS[familia, ano], nome)
                familias.append(FamiliaTse(familia, nome, destino, f"tse:{familia}:{ano}:v1"))
    except (
        zipfile.BadZipFile,
        EOFError,
        csv.Error,
        zlib.error,
        RuntimeError,
        NotImplementedError,
    ) as erro:
        raise ErroColeta(f"ZIP/CSV TSE inválido: {erro}") from erro
    finally:
        # Uma preparação parcial jamais deve parecer pronta para o consumidor.
        if len(familias) != len(recurso.familias):
            for criado in criados:
                criado.unlink(missing_ok=True)
    return tuple(familias)
