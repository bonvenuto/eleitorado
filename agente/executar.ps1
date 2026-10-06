# Execução agendada do agente investigador (Agendador de Tarefas do Windows; veja agendar.ps1).
# Roda a investigação livre (ou retoma a pausada), grava o log e mostra uma notificação no fim.

$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz
$pasta = Join-Path $raiz "investigacoes"
New-Item -ItemType Directory -Force $pasta | Out-Null
$log = Join-Path $pasta "agendador.log"

"$(Get-Date -Format s) início" | Out-File -Append -Encoding utf8 $log
& uv run agente investigar 2>&1 | Out-File -Append -Encoding utf8 $log
$codigo = $LASTEXITCODE
"$(Get-Date -Format s) fim (código $codigo)" | Out-File -Append -Encoding utf8 $log

$ultima = Join-Path $pasta "ultima.json"
if (($codigo -eq 0 -or $codigo -eq 3) -and (Test-Path $ultima)) {
    $resumo = Get-Content $ultima -Raw -Encoding utf8 | ConvertFrom-Json
    $texto = "Investigação $($resumo.id): $($resumo.situacao), $($resumo.achados) achado(s)."
} else {
    $texto = "A investigação não terminou (código $codigo). Veja investigacoes\agendador.log."
}

try {
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    $modelo = [Windows.UI.Notifications.ToastTemplateType]::ToastText02
    $xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($modelo)
    $textos = $xml.GetElementsByTagName("text")
    $textos.Item(0).AppendChild($xml.CreateTextNode("Agente investigador")) | Out-Null
    $textos.Item(1).AppendChild($xml.CreateTextNode($texto)) | Out-Null
    $app = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
    $notificacao = [Windows.UI.Notifications.ToastNotification]::new($xml)
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show($notificacao)
} catch {
    "$(Get-Date -Format s) notificação não exibida: $_" | Out-File -Append -Encoding utf8 $log
}
exit $codigo
