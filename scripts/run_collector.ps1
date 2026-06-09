# Wrapper executado pelo Agendador de Tarefas.
# Roda o coletor com o Python do .venv. O próprio coletor grava o log em
# scripts\collector.log (não redirecionamos aqui para evitar falso-erro do
# PowerShell ao tratar a saída padrão do Python como erro).
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }   # fallback p/ Python do sistema

& $py "scripts\run_collector.py"
exit $LASTEXITCODE
