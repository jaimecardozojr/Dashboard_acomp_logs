"""Armazenamento local em CSV — para desenvolvimento e fallback offline."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .base import Storage


class LocalStorage(Storage):
    def __init__(self, path: str | Path, columns: list[str], key: str):
        super().__init__(columns, key)
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def read_all(self) -> pd.DataFrame:
        if not self.path.exists():
            return pd.DataFrame(columns=self.columns)
        return pd.read_csv(self.path, dtype={self.key: str})

    def append(self, rows: list[dict]) -> int:
        if not rows:
            return 0
        new_df = pd.DataFrame(rows, columns=self.columns)
        header = not self.path.exists()
        new_df.to_csv(self.path, mode="a", header=header, index=False, encoding="utf-8")
        return len(rows)

    def replace(self, rows: list[dict]) -> int:
        if not rows or not self.path.exists():
            return 0
        df = self.read_all()
        ids = {str(r[self.key]) for r in rows}
        kept = df[~df[self.key].astype(str).isin(ids)]
        updated = pd.DataFrame(rows, columns=self.columns)
        out = pd.concat([kept, updated], ignore_index=True)
        out.to_csv(self.path, index=False, encoding="utf-8")
        return len(rows)
