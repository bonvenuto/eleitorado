"""Tipos preparados pelo adaptador TSE, sem publicação ou transformação."""

from dataclasses import dataclass
from pathlib import Path


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
