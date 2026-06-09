"""Carregamento de configuração (config.yaml + variáveis de ambiente)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent


def _default_config() -> Path:
    """Usa config.yaml (local, fora do git) se existir; senão o modelo versionado."""
    real = ROOT / "config.yaml"
    return real if real.exists() else ROOT / "config.example.yaml"


@dataclass
class Automation:
    key: str
    label: str
    emoji: str = "⚙️"


@dataclass
class Settings:
    logs_root: Path
    automations: list[Automation]
    gestta_task_url: str
    backend: str
    gsheets_spreadsheet: str
    gsheets_worksheet_runs: str
    gsheets_worksheet_tasks: str
    local_path_runs: Path
    local_path_tasks: Path
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def automation_keys(self) -> list[str]:
        return [a.key for a in self.automations]

    def label_for(self, key: str) -> str:
        for a in self.automations:
            if a.key == key:
                return f"{a.emoji} {a.label}"
        return key


def load_settings(config_path: str | Path | None = None) -> Settings:
    """Lê o config.yaml (ou config.example.yaml). STORAGE_BACKEND tem prioridade."""
    path = Path(config_path) if config_path else _default_config()
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    automations = [
        Automation(key=a["key"], label=a.get("label", a["key"]), emoji=a.get("emoji", "⚙️"))
        for a in data.get("automations", [])
    ]

    storage = data.get("storage", {})
    backend = os.environ.get("STORAGE_BACKEND", storage.get("backend", "local"))
    gs = storage.get("gsheets", {})
    local = storage.get("local", {})

    def _abs(p: str) -> Path:
        path = Path(p)
        return path if path.is_absolute() else ROOT / path

    return Settings(
        logs_root=Path(data.get("logs_root", "")),
        automations=automations,
        gestta_task_url=data.get("gestta_task_url", ""),
        backend=backend,
        gsheets_spreadsheet=gs.get("spreadsheet", ""),
        gsheets_worksheet_runs=gs.get("worksheet_runs", "execucoes"),
        gsheets_worksheet_tasks=gs.get("worksheet_tasks", "tarefas"),
        local_path_runs=_abs(local.get("path_runs", "data/execucoes.csv")),
        local_path_tasks=_abs(local.get("path_tasks", "data/tarefas.csv")),
        raw=data,
    )
