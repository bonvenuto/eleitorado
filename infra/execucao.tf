# Conta de serviço do pipeline (GitHub Actions) e as permissões dela no bucket privado.

resource "google_service_account" "pipeline" {
  account_id   = "pipeline"
  display_name = "Pipeline diario (coleta + dbt)"
}

# coletor e dbt usam o próprio projeto como quota project (x-goog-user-project)
resource "google_project_iam_member" "pipeline_service_usage" {
  project = var.projeto
  role    = "roles/serviceusage.serviceUsageConsumer"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_storage_bucket_iam_member" "pipeline_cria_objetos" {
  bucket = google_storage_bucket.dados.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_storage_bucket_iam_member" "pipeline_le_objetos" {
  bucket = google_storage_bucket.dados.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.pipeline.email}"
}

# pipeline (GitHub Actions): sobrescreve e apaga só o estado espelhado do lago; os originais
# continuam só com objectCreator (sem sobrescrever nem apagar)
locals {
  prefixos_estado = ["raw/", "meta/", "estado/"]
}

resource "google_storage_bucket_iam_member" "pipeline_espelha_estado" {
  bucket = google_storage_bucket.dados.name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.pipeline.email}"
  condition {
    title = "estado-do-lago"
    expression = join(" || ", [
      for p in local.prefixos_estado :
      "resource.name.startsWith(\"projects/_/buckets/${google_storage_bucket.dados.name}/objects/${p}\")"
    ])
  }
}
