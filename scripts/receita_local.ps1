# Coleta da base do CNPJ da Receita a partir do computador do mantenedor: a Receita bloqueia os IPs
# do GitHub Actions. Agendada por scripts\agendar_receita.ps1 (semanal; a coleta em si só acontece
# quando a cadência mensal vence); também roda à mão, na raiz do repositório:
#   .\scripts\receita_local.ps1
#
# Usa as credenciais do .env (gcloud isolado em .gcloud\) e grava no bucket de produção, a partir
# de um lago próprio (dados-receita\). Para não brigar com o pipeline diário, que espelha o lago no
# bucket: só roda com ele parado, e só acrescenta arquivos ao bucket (estado salvar --aditivo),
# nunca apaga nem sobrescreve. Log em dados-receita\receita.log.

$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz
. (Join-Path $PSScriptRoot "ambiente.ps1")
$env:ELEITORADO_AMBIENTE = "prod"
$env:ELEITORADO_PREFIXO = ""
$env:ELEITORADO_ORIGEM = "agendada"
$env:ELEITORADO_LAGO = "dados-receita"
$env:ELEITORADO_PUBLICO = "dados-receita/publico"
New-Item -ItemType Directory -Force (Join-Path $raiz "dados-receita\publico\marts") | Out-Null
$log = Join-Path $raiz "dados-receita\receita.log"

function Registrar([string]$texto) {
    "$(Get-Date -Format s) $texto" | Out-File -Append -Encoding utf8 $log
}

function Rodar([string[]]$comando) {
    Registrar ("> " + ($comando -join " "))
    & $comando[0] $comando[1..($comando.Length - 1)] 2>&1 | Out-File -Append -Encoding utf8 $log
    return $LASTEXITCODE
}

function Esperar-Pipeline {
    # o pipeline espelha o lago no bucket: rodando junto, apagaria o que esta coleta enviou
    for ($i = 0; $i -lt 36; $i++) {
        $ativos = gh run list --workflow pipeline.yml --limit 5 --json status `
            --jq '[.[] | select(.status != \"completed\")] | length'
        if ($LASTEXITCODE -ne 0) { throw "gh run list falhou (o gh está autenticado?)" }
        if ([int]$ativos -eq 0) { return }
        Registrar "pipeline em execução; nova verificação em 5 minutos"
        Start-Sleep -Seconds 300
    }
    throw "o pipeline não terminou em 3 horas"
}

$codigo = 1
try {
    Registrar "início"
    Esperar-Pipeline
    if ((Rodar @("uv", "run", "coletor", "estado", "restaurar")) -ne 0) {
        throw "coletor estado restaurar falhou"
    }
    # uma thread: os intermediários grandes em paralelo estouram os 4 GB do DuckDB nesta máquina
    $dbt = @("uv", "run", "dbt", "run", "--project-dir", "dbt", "--profiles-dir", "dbt",
        "--target", "prod", "--select", "+int_rfb__raizes_interesse", "--threads", "1")
    if ((Rodar $dbt) -ne 0) { throw "dbt das raízes de interesse falhou" }
    $codigo = Rodar @("uv", "run", "coletor", "executar", "--grupo", "receita")
    # duas passadas: se um pipeline rodou entre a primeira e o fim dela, ele pode ter apagado o
    # que acabou de subir; a segunda (depois de esperá-lo) devolve o que faltar
    foreach ($passada in 1, 2) {
        Esperar-Pipeline
        if ((Rodar @("uv", "run", "coletor", "estado", "salvar", "--aditivo")) -ne 0) {
            throw "coletor estado salvar --aditivo falhou"
        }
    }
    Registrar "fim (coleta: código $codigo)"
    $texto = if ($codigo -eq 0) { "Coleta concluída." } else { "Coleta com falhas (código $codigo)." }
} catch {
    Registrar "erro: $_"
    $codigo = 1
    $texto = "A coleta não terminou: $_"
}

try {
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    $modelo = [Windows.UI.Notifications.ToastTemplateType]::ToastText02
    $xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($modelo)
    $textos = $xml.GetElementsByTagName("text")
    $textos.Item(0).AppendChild($xml.CreateTextNode("Receita (CNPJ)")) | Out-Null
    $textos.Item(1).AppendChild($xml.CreateTextNode("$texto Veja dados-receita\receita.log.")) | Out-Null
    $app = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
    $notificacao = [Windows.UI.Notifications.ToastNotification]::new($xml)
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show($notificacao)
} catch {
    Registrar "notificação não exibida: $_"
}
exit $codigo
