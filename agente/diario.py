"""Diário de uma investigação: consultas executadas e seus resultados (investigacoes/<id>/)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class RegistroConsulta:
    id: str  # q1, q2, ...
    sql: str
    linhas: int  # linhas salvas (até o limite)
    truncada: bool  # havia mais linhas que o limite salvo
    colunas: list[str]
    sha256: str
    executada_em: str  # ISO 8601, UTC
    duracao_s: float
    papel: str  # investigador ou validador


class Diario:
    def __init__(self, pasta: Path) -> None:
        self.pasta = pasta
        self._arquivo = pasta / "consultas.jsonl"

    def proximo_id(self) -> str:
        return f"q{len(self.consultas()) + 1}"

    def caminho_resultado(self, consulta_id: str) -> Path:
        return self.pasta / "consultas" / f"{consulta_id}.parquet"

    def registrar(self, registro: RegistroConsulta) -> None:
        self.pasta.mkdir(parents=True, exist_ok=True)
        with self._arquivo.open("a", encoding="utf-8") as saida:
            saida.write(json.dumps(asdict(registro), ensure_ascii=False) + "\n")

    def consultas(self) -> dict[str, RegistroConsulta]:
        if not self._arquivo.exists():
            return {}
        registros = {}
        for linha in self._arquivo.read_text(encoding="utf-8").splitlines():
            if linha.strip():
                dados = json.loads(linha)
                registros[dados["id"]] = RegistroConsulta(**dados)
        return registros
