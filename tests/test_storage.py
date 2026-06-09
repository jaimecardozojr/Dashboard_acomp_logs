"""Testes do LocalStorage (genérico) e do upsert de execuções do collector."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from log_dashboard.collector import _sync_runs  # noqa: E402
from log_dashboard.models import RunRecord  # noqa: E402
from log_dashboard.storage.local import LocalStorage  # noqa: E402

RUN_COLS = RunRecord.columns()


def _rec(run_id: str, status: str) -> RunRecord:
    return RunRecord(
        run_id=run_id, automation="ferias", date="2026-06-09",
        start_time="2026-06-09T07:00:00", end_time="2026-06-09T07:01:00",
        duration_seconds=60, status=status, attempts=1, tasks_generated=0,
        new_records=0, pending_tasks=0, warnings=0, errors=0, criticals=0,
        last_error="", log_file="f.log",
    )


def _runs_storage(tmp_path) -> LocalStorage:
    return LocalStorage(tmp_path / "e.csv", columns=RUN_COLS, key="run_id")


def test_append_new_dedup(tmp_path):
    st = _runs_storage(tmp_path)
    rows = [_rec("a", "sucesso").to_row(), _rec("b", "falha").to_row()]
    assert st.append_new(rows) == 2
    assert st.append_new([_rec("a", "sucesso").to_row()]) == 0  # idempotente
    assert len(st.read_all()) == 2


def test_replace_por_chave(tmp_path):
    st = _runs_storage(tmp_path)
    st.append_new([_rec("x", "incompleto").to_row()])
    st.replace([_rec("x", "sucesso").to_row()])
    assert len(st.read_all()) == 1
    assert st.read_all().iloc[0]["status"] == "sucesso"


def test_sync_runs_upsert_incompleto(tmp_path):
    st = _runs_storage(tmp_path)
    assert _sync_runs(st, [_rec("x", "incompleto")]) == 1
    # mesma sessão, agora concluída -> atualiza, não duplica, não conta como nova
    assert _sync_runs(st, [_rec("x", "sucesso")]) == 0
    df = st.read_all()
    assert len(df) == 1
    assert df.iloc[0]["status"] == "sucesso"


def test_sync_runs_nao_reabre_concluido(tmp_path):
    st = _runs_storage(tmp_path)
    _sync_runs(st, [_rec("x", "sucesso")])
    assert _sync_runs(st, [_rec("x", "falha")]) == 0
    assert st.read_all().iloc[0]["status"] == "sucesso"
