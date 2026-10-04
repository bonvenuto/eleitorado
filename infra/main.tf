provider "google" {
  project               = var.projeto
  region                = var.regiao
  billing_project       = var.projeto
  user_project_override = true
}

resource "google_project_service" "apis" {
  for_each = toset([
    "bigquery.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "serviceusage.googleapis.com",
    "storage.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}
