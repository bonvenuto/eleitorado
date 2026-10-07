"""Tipos preparados pelo adaptador TSE, sem publicação ou transformação."""

from dataclasses import dataclass
from pathlib import Path

from coletor.dbt import ResultadoDbt


@dataclass(frozen=True)
class FamiliaTse:
    """Um membro consolidado validado, preservando integralmente seu CSV."""

    familia: str
    membro: str
    csv: Path
    layout_id: str


@dataclass(frozen=True)
class VersaoTse:
    """Uma versão física privada, sem estado de seleção ou publicação."""

    recurso_id: str
    ano: int
    versao_id: str
    sha256_zip: str
    familias: dict[str, str]
    hashes: dict[str, str]
    layouts: dict[str, str]
    sha256_semantico: str


@dataclass(frozen=True)
class SelecaoTse:
    """Vetor privado explícito; cada recurso/ano escolhe uma única versão."""

    selecao_id: str
    versoes: dict[str, str]


@dataclass(frozen=True)
class ReciboValidacaoTse:
    """Vínculo verificável entre seleção, execução dbt e arquivos preparados."""

    selecao_digest: str
    execucao_id: str
    entradas_digest: str
    saida_digest: str
    resultado: ResultadoDbt
