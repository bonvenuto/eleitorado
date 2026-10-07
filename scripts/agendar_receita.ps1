# Registra a coleta da Receita (scripts\receita_local.ps1) no Agendador de Tarefas do Windows.
# Rode uma vez, no PowerShell, na raiz do repositório:  .\scripts\agendar_receita.ps1
# Para mudar o dia ou a hora:  .\scripts\agendar_receita.ps1 -Dia Sunday -Hora 23:00
# Semanal de madrugada, longe do pipeline diário (10:30 UTC); a coleta em si só acontece quando a
# cadência mensal dos recursos vence, nas outras semanas é rápida.
param(
    [string]$Dia = "Monday",
    [string]$Hora = "02:00"
)

$raiz = Split-Path -Parent $PSScriptRoot
$script = Join-Path $raiz "scripts\receita_local.ps1"
$acao = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`"" -WorkingDirectory $raiz
$gatilho = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Dia -At $Hora
$opcoes = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 5)
Register-ScheduledTask -TaskName "eleitorado-receita" -Action $acao -Trigger $gatilho `
    -Settings $opcoes -Description "Coleta da base do CNPJ da Receita (eleitorado)" -Force | Out-Null
Write-Output "Tarefa 'eleitorado-receita' agendada: $Dia às $Hora (roda assim que possível se a máquina estiver desligada no horário)."
