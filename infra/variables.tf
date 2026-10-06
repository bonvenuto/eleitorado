variable "projeto" {
  description = "ID do projeto GCP dedicado ao eleitorado"
  type        = string
}

variable "regiao" {
  description = "Região de todos os recursos"
  type        = string
  default     = "southamerica-east1"
}

variable "github_repo" {
  description = "Repositorio autorizado a autenticar no GCP pelo GitHub Actions (dono/nome)"
  type        = string
  default     = "bonvenuto/eleitorado"
}

variable "conta_faturamento" {
  description = "ID da conta de faturamento, usado no orcamento"
  type        = string
}

variable "orcamento_mensal_brl" {
  description = "Orcamento mensal em reais; a conta de faturamento e em BRL (R$ 30 sao cerca de US$ 5)"
  type        = number
  default     = 30
}
