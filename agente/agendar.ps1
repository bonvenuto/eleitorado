# Registra a execução semanal do agente investigador no Agendador de Tarefas do Windows.
# Rode uma vez, no PowerShell, na raiz do repositório:  .\agente\agendar.ps1
# Para mudar o dia ou a hora:  .\agente\agendar.ps1 -Dia Tuesday -Hora 10:30
param(
    [string]$Dia = "Monday",
    [string]$Hora = "09:00"
)

$raiz = Split-Path -Parent $PSScriptRoot
$script = Join-Path $raiz "agente\executar.ps1"
$acao = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`"" -WorkingDirectory $raiz
$gatilho = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Dia -At $Hora
$opcoes = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 4)
Register-ScheduledTask -TaskName "eleitorado-agente-investigador" -Action $acao -Trigger $gatilho `
    -Settings $opcoes -Description "Agente investigador L1 do eleitorado (semanal)" -Force | Out-Null
Write-Output "Tarefa 'eleitorado-agente-investigador' agendada: $Dia às $Hora (roda assim que possível se a máquina estiver desligada no horário)."
