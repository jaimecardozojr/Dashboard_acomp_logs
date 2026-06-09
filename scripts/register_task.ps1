<#
.SYNOPSIS
  Registra (ou atualiza) a tarefa agendada que roda o coletor automaticamente.

.DESCRIPTION
  Cria uma tarefa no Agendador do Windows que executa scripts\run_collector.ps1
  a cada N minutos, na SUA sessão (necessário porque o drive P: só existe quando
  você está logado). Não exige administrador.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1
  powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1 -IntervalMinutes 15

.NOTES
  Remover:  Unregister-ScheduledTask -TaskName "DashboardAcompLogs-Coletor" -Confirm:$false
  Rodar já: Start-ScheduledTask -TaskName "DashboardAcompLogs-Coletor"
#>
param(
    [int]$IntervalMinutes = 30,
    [string]$TaskName = "DashboardAcompLogs-Coletor"
)
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$wrapper = Join-Path $root "scripts\run_collector.ps1"
if (-not (Test-Path $wrapper)) { throw "Wrapper não encontrado: $wrapper" }

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$wrapper`"" `
    -WorkingDirectory $root

# Dispara em ~2 min e repete a cada N minutos, indefinidamente.
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) `
    -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15)

# Roda como o usuário atual, apenas quando logado (mantém o drive P: acessível).
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal `
    -Description "Lê os logs das automações e atualiza a planilha do Google Sheets." `
    -Force | Out-Null

Write-Host "OK: tarefa '$TaskName' registrada (roda a cada $IntervalMinutes min)." -ForegroundColor Green
Write-Host "Testar agora:  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "Ver status:    Get-ScheduledTask -TaskName '$TaskName' | Get-ScheduledTaskInfo"
Write-Host "Remover:       Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:0"
