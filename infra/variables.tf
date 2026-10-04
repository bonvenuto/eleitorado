variable "projeto" {
  description = "ID do projeto GCP dedicado ao eleitorado"
  type        = string
}

variable "regiao" {
  description = "Região de todos os recursos"
  type        = string
  default     = "southamerica-east1"
}
