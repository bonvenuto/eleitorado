resource "google_storage_bucket" "dados" {
  name                        = "${var.projeto}-dados"
  location                    = var.regiao
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  # Objetos sobrescritos ou apagados (raw substituído, históricos regravados) podem ser
  # recuperados por 30 dias.
  soft_delete_policy {
    retention_duration_seconds = 2592000
  }

  # Originais nunca são apagados; depois de 30 dias vão para a classe mais barata.
  lifecycle_rule {
    condition {
      age                   = 30
      matches_prefix        = ["originais/", "dev/originais/", "paralelo/originais/"]
      matches_storage_class = ["STANDARD"]
    }
    action {
      type          = "SetStorageClass"
      storage_class = "ARCHIVE"
    }
  }

  # O Parquet de carga é descartável: pode ser refeito a partir do original.
  lifecycle_rule {
    condition {
      age            = 7
      matches_prefix = ["carga/", "dev/carga/"]
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.apis]
}

locals {
  datasets = ["meta", "raw_camara", "raw_senado", "raw_cgu", "raw_ibge", "replay"]
}

resource "google_bigquery_dataset" "prod" {
  for_each    = toset(local.datasets)
  dataset_id  = each.value
  location    = var.regiao
  description = "Eleitorado: ${each.value}"
  depends_on  = [google_project_service.apis]
}

resource "google_bigquery_dataset" "dev" {
  for_each                    = toset(local.datasets)
  dataset_id                  = "${each.value}_dev"
  location                    = var.regiao
  description                 = "Eleitorado (desenvolvimento): ${each.value}"
  default_table_expiration_ms = 2592000000 # 30 dias: dados de teste não se acumulam
  depends_on                  = [google_project_service.apis]
}

resource "google_bigquery_dataset" "ci" {
  dataset_id                  = "ci"
  location                    = var.regiao
  description                 = "Eleitorado: relacoes temporarias dos testes unitarios do dbt"
  default_table_expiration_ms = 86400000 # 1 dia
  depends_on                  = [google_project_service.apis]
}

# Camadas do dbt em produção (em dev, o dbt cria dev_<usuario>_* com a conta de quem roda)
locals {
  datasets_dbt = ["staging", "intermediate", "marts"]
}

resource "google_bigquery_dataset" "dbt" {
  for_each    = toset(local.datasets_dbt)
  dataset_id  = each.value
  location    = var.regiao
  description = "Eleitorado (dbt): ${each.value}"
  depends_on  = [google_project_service.apis]
}

output "bucket_dados" {
  value = google_storage_bucket.dados.name
}
