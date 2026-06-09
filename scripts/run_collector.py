"""Entrypoint do robô. Rode periodicamente (Agendador de Tarefas do Windows).

Exemplos:
    python scripts/run_collector.py
    python scripts/run_collector.py --backend local
    python scripts/run_collector.py --config config.yaml
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# Garante que o pacote seja importável quando rodado de qualquer lugar
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from log_dashboard.collector import collect  # noqa: E402
from log_dashboard.config import load_settings  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Coletor de logs de automações")
    ap.add_argument("--config", default=None, help="padrão: config.yaml (ou config.example.yaml)")
    ap.add_argument("--backend", choices=["gsheets", "local"], help="sobrescreve o config.yaml")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if args.backend:
        os.environ["STORAGE_BACKEND"] = args.backend

    settings = load_settings(args.config)
    result = collect(settings)

    logging.info(
        "Concluído (backend=%s): execuções %d/%d novas · tarefas %d/%d novas",
        result.backend, result.runs_written, result.runs_parsed,
        result.tasks_written, result.tasks_parsed,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
