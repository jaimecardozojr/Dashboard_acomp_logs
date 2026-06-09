"""Carregamento e preparo dos dados para o dashboard.

Decide a fonte de dados:
  - secrets["storage_backend"] == "gsheets"  -> lê do Google Sheets (online);
  - caso contrário                            -> lê do CSV local (dev).
Se o Sheets estiver configurado mas faltarem credenciais, cai no CSV local.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from log_dashboard.config import load_settings  # noqa: E402
from log_dashboard.models import RunRecord, TaskRecord  # noqa: E402
from log_dashboard.storage import Kind, get_storage  # noqa: E402

NUMERIC_COLS = [
    "duration_seconds", "attempts", "tasks_generated", "new_records",
    "pending_tasks", "warnings", "errors", "criticals",
]


def _to_number(series: pd.Series) -> pd.Series:
    """Converte para número tolerando o formato pt-BR do Google Sheets
    (ex.: '94,7' ou '1.097,8'), além do formato com ponto decimal."""
    s = series.astype(str).str.strip()
    both = s.str.contains(r"\.") & s.str.contains(",")
    s = s.mask(both, s.str.replace(".", "", regex=False))  # remove ponto de milhar
    s = s.str.replace(",", ".", regex=False)               # vírgula -> ponto decimal
    return pd.to_numeric(s, errors="coerce").fillna(0)


def _safe_secrets() -> dict:
    """Lê st.secrets sem quebrar quando não há secrets.toml (dev local)."""
    try:
        return dict(st.secrets)
    except Exception:
        return {}


def _settings_from_secrets():
    """Carrega o config.yaml e aplica overrides vindos dos secrets (online)."""
    settings = load_settings()
    secrets = _safe_secrets()
    settings.backend = secrets.get("storage_backend", settings.backend)
    if "spreadsheet" in secrets:
        settings.gsheets_spreadsheet = secrets["spreadsheet"]
    if "gestta_task_url" in secrets:
        settings.gestta_task_url = secrets["gestta_task_url"]
    return settings, secrets


def gestta_url() -> str:
    """URL-modelo da tarefa no Gestta (secrets têm prioridade sobre o config)."""
    settings, _ = _settings_from_secrets()
    return settings.gestta_task_url


def _read_with_fallback(kind: Kind, key_col: str) -> tuple[pd.DataFrame, str]:
    """Lê a entidade `kind` do backend configurado, com fallback p/ CSV local."""
    settings, secrets = _settings_from_secrets()
    creds = dict(secrets["gcp_service_account"]) if "gcp_service_account" in secrets else None
    try:
        storage = get_storage(settings, kind, credentials_dict=creds)
        return storage.read_all(), storage.__class__.__name__
    except Exception as exc:  # creds ausentes / falha de conexão com o Sheets
        settings.backend = "local"
        df = get_storage(settings, kind).read_all()
        if df.empty:
            raise exc  # sem Sheets E sem CSV: mostra o erro original
        return df, "fallback-local"


@st.cache_data(ttl=300, show_spinner="Carregando execuções...")
def load_runs() -> pd.DataFrame:
    """Lê todas as execuções e normaliza tipos. Cache de 5 min."""
    df, source = _read_with_fallback("runs", "run_id")
    st.session_state["data_source"] = source

    if df.empty:
        return pd.DataFrame(columns=RunRecord.columns())

    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = _to_number(df[col])

    df["start_dt"] = pd.to_datetime(df["start_time"], errors="coerce")
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    df["hour"] = df["start_dt"].dt.hour
    df["last_error"] = df.get("last_error", "").fillna("")
    df = df.dropna(subset=["start_dt"]).sort_values("start_dt")
    return df


@st.cache_data(ttl=300, show_spinner="Carregando tarefas...")
def load_tasks() -> pd.DataFrame:
    """Lê todas as tarefas criadas e normaliza tipos. Cache de 5 min."""
    df, _ = _read_with_fallback("tasks", "task_number")
    if df.empty:
        return pd.DataFrame(columns=TaskRecord.columns())

    df["task_number"] = df["task_number"].astype(str)
    df["created_dt"] = pd.to_datetime(df["created_at"], errors="coerce")
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    for col in ("person", "title"):
        if col in df.columns:
            df[col] = df[col].fillna("")
    df = df.sort_values("created_dt", ascending=False)
    return df


def filter_runs(
    df: pd.DataFrame,
    automations: list[str],
    statuses: list[str],
    date_range: tuple,
) -> pd.DataFrame:
    out = df
    if automations:
        out = out[out["automation"].isin(automations)]
    if statuses:
        out = out[out["status"].isin(statuses)]
    if date_range and len(date_range) == 2 and all(date_range):
        start, end = date_range
        out = out[(out["date"] >= start) & (out["date"] <= end)]
    return out


def gestta_link(template: str, task_number: str, task_date) -> str:
    """Monta o link da tarefa no Gestta. searchText = nº sem zeros à esquerda;
    o intervalo de datas cobre o mês da tarefa."""
    if not template:
        return ""
    search = str(task_number).lstrip("0") or str(task_number)
    period = pd.Period(pd.Timestamp(task_date), freq="M")
    start = period.start_time.strftime("%Y-%m-%dT00:00:00-03:00")
    end = period.end_time.strftime("%Y-%m-%dT23:59:59-03:00")
    return template.format(search=search, start=start, end=end)


def add_task_links(df: pd.DataFrame, template: str) -> pd.DataFrame:
    """Acrescenta a coluna `task_link` com o link direto de cada tarefa."""
    out = df.copy()
    out["task_link"] = [
        gestta_link(template, num, dt)
        for num, dt in zip(out["task_number"], out["date"])
    ]
    return out


def filter_tasks(df: pd.DataFrame, automations: list[str], date_range: tuple) -> pd.DataFrame:
    out = df
    if automations:
        out = out[out["automation"].isin(automations)]
    if date_range and len(date_range) == 2 and all(date_range):
        start, end = date_range
        out = out[(out["date"] >= start) & (out["date"] <= end)]
    return out
