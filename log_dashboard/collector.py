"""O 'robô': lê os logs, faz o parse e sincroniza com o armazenamento."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from .config import Settings, load_settings
from .models import RunRecord
from .parser import parse_all, parse_tasks_all
from .storage import Storage, get_storage

log = logging.getLogger("collector")


@dataclass
class CollectResult:
    runs_parsed: int
    runs_written: int
    tasks_parsed: int
    tasks_written: int
    backend: str


def _sync_runs(storage: Storage, records: list[RunRecord]) -> int:
    """Grava execuções novas e atualiza as que estavam 'incompleto' e agora
    têm desfecho (a última sessão do dia pode ser capturada em andamento)."""
    df = storage.read_all()
    existing: dict[str, str] = {}
    if not df.empty and "run_id" in df.columns:
        existing = dict(zip(df["run_id"].astype(str), df["status"].astype(str)))

    novos = [r for r in records if r.run_id not in existing]
    stale = [
        r for r in records
        if existing.get(r.run_id) == "incompleto" and r.status != "incompleto"
    ]

    written = storage.append([r.to_row() for r in novos]) if novos else 0
    if stale:
        storage.replace([r.to_row() for r in stale])
    return written


def collect(settings: Settings | None = None) -> CollectResult:
    """Pipeline completo: parse dos logs -> sync de execuções e tarefas."""
    settings = settings or load_settings()
    log.info("Lendo logs em %s", settings.logs_root)

    # Execuções
    records = parse_all(settings.logs_root, settings.automation_keys)
    runs_storage = get_storage(settings, "runs")
    runs_written = _sync_runs(runs_storage, records)
    log.info("Execuções: %d lidas, %d novas gravadas", len(records), runs_written)

    # Tarefas criadas (append-only por número único)
    tasks = parse_tasks_all(settings.logs_root, settings.automation_keys)
    tasks_storage = get_storage(settings, "tasks")
    tasks_written = tasks_storage.append_new([t.to_row() for t in tasks])
    log.info("Tarefas: %d lidas, %d novas gravadas", len(tasks), tasks_written)

    return CollectResult(
        runs_parsed=len(records),
        runs_written=runs_written,
        tasks_parsed=len(tasks),
        tasks_written=tasks_written,
        backend=settings.backend,
    )
