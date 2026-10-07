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
