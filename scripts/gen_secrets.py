"""Gera .streamlit/secrets.toml a partir do service_account.json + config.yaml.

O arquivo gerado fica fora do git (.gitignore) e serve tanto para testar o
dashboard localmente no modo gsheets quanto para copiar/colar no Streamlit Cloud
(Settings -> Secrets).

Uso:  python scripts/gen_secrets.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from log_dashboard.config import load_settings  # noqa: E402

SA_FIELDS = [
    "type", "project_id", "private_key_id", "private_key", "client_email",
    "client_id", "auth_uri", "token_uri", "auth_provider_x509_cert_url",
    "client_x509_cert_url", "universe_domain",
]


def _toml_str(value: str) -> str:
    """String TOML básica: escapa barra, aspas e quebras de linha."""
    s = str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{s}"'


def main() -> int:
    sa_path = ROOT / "service_account.json"
    if not sa_path.exists():
        print("ERRO: service_account.json não encontrado na raiz.")
        return 1

    sa = json.loads(sa_path.read_text(encoding="utf-8"))
    s = load_settings()

    lines = [
        f"storage_backend = {_toml_str('gsheets')}",
        f"spreadsheet = {_toml_str(s.gsheets_spreadsheet)}",
        f"worksheet = {_toml_str(s.gsheets_worksheet_runs)}",
        f"gestta_task_url = {_toml_str(s.gestta_task_url)}",
        "",
        "[gcp_service_account]",
    ]
    lines += [f"{k} = {_toml_str(sa[k])}" for k in SA_FIELDS if k in sa]

    out = ROOT / ".streamlit" / "secrets.toml"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Gerado: {out}  ({len(lines)} linhas)")
    print("Cole o conteúdo desse arquivo em Streamlit Cloud -> Settings -> Secrets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
