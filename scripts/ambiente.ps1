# Carrega as variáveis de um arquivo .env na sessão atual do PowerShell.
# Uso: . .\scripts\ambiente.ps1             (desenvolvimento: .env)
#      . .\scripts\ambiente.ps1 .env.prod   (produção)
param([string]$Arquivo = ".env")
$caminho = Join-Path (Split-Path $PSScriptRoot -Parent) $Arquivo
if (-not (Test-Path $caminho)) { throw "Arquivo não encontrado: $caminho" }
Get-Content $caminho | ForEach-Object {
    if ($_ -match '^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*?)\s*$') {
        Set-Item -Path "Env:$($Matches[1])" -Value $Matches[2]
    }
}
Write-Host "Ambiente $env:ELEITORADO_AMBIENTE carregado (projeto $env:ELEITORADO_PROJETO)"
