"""Interface comum de armazenamento, genérica por schema (colunas + chave)."""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class Storage(ABC):
    """Contrato mínimo para qualquer backend (CSV, Sheets, banco...).

    É agnóstico ao tipo de registro: recebe as `columns` e a coluna-chave
    `key` usada para deduplicação/upsert. Opera sobre listas de dicts.
    """

    def __init__(self, columns: list[str], key: str):
        self.columns = columns
        self.key = key

    @abstractmethod
    def read_all(self) -> pd.DataFrame:
        """Todas as linhas como DataFrame (vazio se não houver)."""

    @abstractmethod
    def append(self, rows: list[dict]) -> int:
        """Acrescenta linhas. Retorna quantas foram gravadas."""

    @abstractmethod
    def replace(self, rows: list[dict]) -> int:
        """Sobrescreve linhas existentes casadas por `key`. Retorna quantas."""

    def existing_keys(self) -> set[str]:
        df = self.read_all()
        if df.empty or self.key not in df.columns:
            return set()
        return set(df[self.key].astype(str))

    def append_new(self, rows: list[dict]) -> int:
        """Grava apenas linhas cuja chave ainda não existe (idempotente)."""
        known = self.existing_keys()
        novos = [r for r in rows if str(r[self.key]) not in known]
        return self.append(novos) if novos else 0
