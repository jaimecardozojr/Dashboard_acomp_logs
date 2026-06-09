"""Armazenamento no Google Sheets — ponte entre o robô (local) e o dashboard (online).

Autenticação por conta de serviço, de três formas (nesta ordem):
  1. credentials_dict passado no construtor (ex.: st.secrets no dashboard online);
  2. variável de ambiente GOOGLE_APPLICATION_CREDENTIALS (caminho do JSON);
  3. arquivo service_account.json na raiz do projeto.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import pandas as pd

from .base import Storage

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
ROOT = Path(__file__).resolve().parent.parent.parent


def _col_letter(n: int) -> str:
    """1 -> A, 26 -> Z, 27 -> AA (notação de coluna A1 do Sheets)."""
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


class GSheetsStorage(Storage):
    def __init__(
        self,
        spreadsheet: str,
        worksheet: str,
        columns: list[str],
        key: str,
        credentials_dict: Optional[dict] = None,
        value_input_option: str = "USER_ENTERED",
    ):
        super().__init__(columns, key)
        self.spreadsheet_ref = spreadsheet
        self.worksheet_name = worksheet
        self._credentials_dict = credentials_dict
        # RAW preserva texto (ex.: nº de tarefa "0000015730" sem virar número)
        self.value_input_option = value_input_option
        self._ws = None  # conexão preguiçosa

    # ------------------------------------------------------------------ auth
    def _client(self):
        import gspread
        from google.oauth2.service_account import Credentials

        if self._credentials_dict:
            creds = Credentials.from_service_account_info(self._credentials_dict, scopes=SCOPES)
            return gspread.authorize(creds)

        env_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        candidates = [env_path] if env_path else []
        candidates.append(str(ROOT / "service_account.json"))
        for cand in candidates:
            if cand and Path(cand).exists():
                creds = Credentials.from_service_account_file(cand, scopes=SCOPES)
                return gspread.authorize(creds)

        raise FileNotFoundError(
            "Credenciais do Google não encontradas. Defina GOOGLE_APPLICATION_CREDENTIALS, "
            "coloque service_account.json na raiz, ou passe credentials_dict."
        )

    def _open_spreadsheet(self, client):
        # Aceita tanto o nome quanto a chave (ID) da planilha.
        try:
            return client.open_by_key(self.spreadsheet_ref)
        except Exception:
            return client.open(self.spreadsheet_ref)

    def _worksheet(self):
        if self._ws is not None:
            return self._ws
        import gspread

        client = self._client()
        sh = self._open_spreadsheet(client)
        try:
            ws = sh.worksheet(self.worksheet_name)
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title=self.worksheet_name, rows=1000, cols=len(self.columns))
            ws.append_row(self.columns, value_input_option="RAW")
        if not ws.row_values(1):
            ws.append_row(self.columns, value_input_option="RAW")
        self._ws = ws
        return ws

    # --------------------------------------------------------------- storage
    def read_all(self) -> pd.DataFrame:
        ws = self._worksheet()
        rows = ws.get_all_records()  # 1ª linha = cabeçalho
        if not rows:
            return pd.DataFrame(columns=self.columns)
        df = pd.DataFrame(rows)
        if self.key in df.columns:
            df[self.key] = df[self.key].astype(str)
        return df

    def append(self, rows: list[dict]) -> int:
        if not rows:
            return 0
        ws = self._worksheet()
        payload = [[r[c] for c in self.columns] for r in rows]
        ws.append_rows(payload, value_input_option=self.value_input_option)
        return len(rows)

    def replace(self, rows: list[dict]) -> int:
        """Atualiza linhas existentes casando por `key` (poucas por execução)."""
        if not rows:
            return 0
        ws = self._worksheet()
        key_vals = ws.col_values(self.columns.index(self.key) + 1)  # inclui cabeçalho
        pos = {str(v): i + 1 for i, v in enumerate(key_vals)}  # chave -> nº da linha

        batch, last_col = [], _col_letter(len(self.columns))
        for r in rows:
            row_n = pos.get(str(r[self.key]))
            if not row_n:
                continue
            values = [r[c] for c in self.columns]
            batch.append({"range": f"A{row_n}:{last_col}{row_n}", "values": [values]})

        if batch:
            ws.batch_update(batch, value_input_option=self.value_input_option)
        return len(batch)
