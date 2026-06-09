# Sobe o dashboard localmente.
# Uso:  ./scripts/run_dashboard.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
streamlit run app/streamlit_app.py
