# Imagem, contas de serviço, Cloud Run Job e agendamento diário.

resource "google_artifact_registry_repository" "eleitorado" {
  location      = var.regiao
  repository_id = "eleitorado"
  format        = "DOCKER"

  cleanup_policy_dry_run = false
  cleanup_policies {
    id     = "manter-2-recentes"
    action = "KEEP"
    most_recent_versions {
      keep_count = 2
    }
  }
  cleanup_policies {
    id     = "apagar-antigas"
    action = "DELETE"
    condition {
      tag_state  = "ANY"
      older_than = "86400s"
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_service_account" "pipeline" {
  account_id   = "pipeline"
  display_name = "Pipeline diario (coleta + dbt)"
}

resource "google_service_account" "scheduler" {
  account_id   = "scheduler"
  display_name = "Cloud Scheduler: dispara o job"
}

resource "google_service_account" "deployer" {
  account_id   = "deployer"
  display_name = "GitHub Actions: publica a imagem e atualiza o job"
}

resource "google_service_account" "ci" {
  account_id   = "ci-github"
  display_name = "GitHub Actions: vigia e testes do dbt"
}

# pipeline: grava nos datasets de produção e só cria objetos no bucket (sem apagar nem sobrescrever)
resource "google_project_iam_member" "pipeline_job_user" {
  project = var.projeto
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

# coletor e dbt usam o próprio projeto como quota project (x-goog-user-project)
resource "google_project_iam_member" "pipeline_service_usage" {
  project = var.projeto
  role    = "roles/serviceusage.serviceUsageConsumer"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_bigquery_dataset_iam_member" "pipeline_editor" {
  for_each   = toset(local.datasets)
  dataset_id = google_bigquery_dataset.prod[each.key].dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_bigquery_dataset_iam_member" "pipeline_edita_dbt" {
  for_each   = toset(local.datasets_dbt)
  dataset_id = google_bigquery_dataset.dbt[each.key].dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.pipeline.email}"
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

resource "google_cloud_run_v2_job" "pipeline" {
  name                = "pipeline"
  location            = var.regiao
  deletion_protection = false

  template {
    task_count = 1
    template {
      service_account = google_service_account.pipeline.email
      timeout         = "3600s"
      max_retries     = 1
      containers {
        image = var.imagem_inicial
        args  = ["pipeline"]
        resources {
          limits = {
            cpu    = "1"
            memory = "2Gi"
          }
        }
        env {
          name  = "ELEITORADO_PROJETO"
          value = var.projeto
        }
        env {
          name  = "ELEITORADO_BUCKET"
          value = google_storage_bucket.dados.name
        }
        env {
          name  = "ELEITORADO_REGIAO"
          value = var.regiao
        }
        env {
          name  = "ELEITORADO_AMBIENTE"
          value = "prod"
        }
        env {
          name  = "ELEITORADO_ORIGEM"
          value = "agendada"
        }
      }
    }
  }

  # A imagem é trocada pelo workflow de deploy; o Terraform não a reverte.
  lifecycle {
    ignore_changes = [
      template[0].template[0].containers[0].image,
      client,
      client_version,
    ]
  }

  depends_on = [google_project_service.apis]
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_invoca" {
  name     = google_cloud_run_v2_job.pipeline.name
  location = var.regiao
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}

resource "google_cloud_scheduler_job" "pipeline_diario" {
  name             = "pipeline-diario"
  region           = var.regiao
  schedule         = "30 7 * * *"
  time_zone        = "America/Sao_Paulo"
  attempt_deadline = "320s"

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.projeto}/locations/${var.regiao}/jobs/${google_cloud_run_v2_job.pipeline.name}:run"
    oauth_token {
      service_account_email = google_service_account.scheduler.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }

  depends_on = [google_cloud_run_v2_job_iam_member.scheduler_invoca]
}
