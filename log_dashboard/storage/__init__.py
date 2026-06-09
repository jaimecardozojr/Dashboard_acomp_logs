"""Camada de armazenamento trocável (local CSV / Google Sheets / futuro: DB)."""
from __future__ import annotations

from typing import Literal, Optional

from ..config import Settings
from ..models import RunRecord, TaskRecord
from .base import Storage
from .local import LocalStorage

Kind = Literal["runs", "tasks"]

# Schema (colunas + chave) de cada entidade
_SCHEMAS = {
    "runs": (RunRecord.columns(), "run_id"),
    "tasks": (TaskRecord.columns(), "task_number"),
}


def get_storage(
    settings: Settings,
    kind: Kind,
    credentials_dict: Optional[dict] = None,
) -> Storage:
    """Devolve o backend configurado para a entidade `kind` ('runs' | 'tasks')."""
    columns, key = _SCHEMAS[kind]
    backend = settings.backend.lower()

    if backend == "gsheets":
        from .gsheets import GSheetsStorage  # import tardio (não exige gspread no modo local)

        worksheet = (
            settings.gsheets_worksheet_runs if kind == "runs"
            else settings.gsheets_worksheet_tasks
        )
        # Tarefas vão como texto (RAW) p/ preservar zeros à esquerda do nº.
        input_option = "USER_ENTERED" if kind == "runs" else "RAW"
        return GSheetsStorage(
            spreadsheet=settings.gsheets_spreadsheet,
            worksheet=worksheet,
            columns=columns,
            key=key,
            credentials_dict=credentials_dict,
            value_input_option=input_option,
        )
    if backend == "local":
        path = settings.local_path_runs if kind == "runs" else settings.local_path_tasks
        return LocalStorage(path, columns=columns, key=key)

    raise ValueError(f"Backend de storage desconhecido: {settings.backend!r}")


__all__ = ["Storage", "LocalStorage", "get_storage", "Kind"]
