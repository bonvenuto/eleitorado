# Configura o projeto GCP do eleitorado depois do login.
# Pré-requisito (uma vez, no PC, com o .env carregado):
#   . .\scripts\ambiente.ps1
#   gcloud auth login
#   gcloud auth application-default login
# Uso: . .\scripts\ambiente.ps1; .\scripts\configurar-gcp.ps1 -ContaFaturamento XXXXXX-XXXXXX-XXXXXX
param([Parameter(Mandatory = $true)][string]$ContaFaturamento)
# gcloud escreve progresso em stderr: o controle de erro é pelo código de saída
$ErrorActionPreference = "Continue"
$projeto = $env:ELEITORADO_PROJETO
if (-not $projeto) { throw "Carregue o .env antes: . .\scripts\ambiente.ps1" }

function Existe([scriptblock]$consulta) {
    & $consulta 2>&1 | Out-Null
    return $LASTEXITCODE -eq 0
}

function Executar([string]$descricao, [scriptblock]$comando) {
    Write-Host "==> $descricao"
    & $comando
    if ($LASTEXITCODE -ne 0) { throw "Falhou: $descricao" }
}

if (-not (Existe { gcloud projects describe $projeto --format="value(projectId)" })) {
    Executar "criar projeto $projeto" { gcloud projects create $projeto --name="dados publicos" }
}
Executar "vincular faturamento" { gcloud billing projects link $projeto --billing-account=$ContaFaturamento }
Executar "projeto padrão" { gcloud config set project $projeto }
Executar "habilitar APIs básicas" {
    gcloud services enable serviceusage.googleapis.com cloudresourcemanager.googleapis.com storage.googleapis.com
}
Executar "quota project do ADC" { gcloud auth application-default set-quota-project $projeto }

$estado = "gs://$projeto-tfstate"
if (-not (Existe { gcloud storage buckets describe $estado --format="value(name)" })) {
    Executar "bucket de estado do Terraform" {
        gcloud storage buckets create $estado --location=southamerica-east1 --uniform-bucket-level-access --public-access-prevention
    }
}

Executar "terraform init" { terraform -chdir=infra init -input=false "-backend-config=bucket=$projeto-tfstate" "-backend-config=prefix=infra" }
Executar "terraform apply" { terraform -chdir=infra apply -input=false -auto-approve "-var=projeto=$projeto" }
Write-Host "Pronto. Datasets:"
bq ls --project_id=$projeto
