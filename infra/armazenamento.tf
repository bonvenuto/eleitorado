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
      matches_prefix        = ["originais/", "dev/originais/"]
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

output "bucket_dados" {
  value = google_storage_bucket.dados.name
}
