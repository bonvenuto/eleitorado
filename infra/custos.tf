# Orçamento mensal com alertas por e-mail aos administradores da conta de faturamento.

data "google_project" "atual" {}

resource "google_billing_budget" "mensal" {
  billing_account = var.conta_faturamento
  display_name    = "eleitorado-mensal"

  budget_filter {
    projects               = ["projects/${data.google_project.atual.number}"]
    credit_types_treatment = "EXCLUDE_ALL_CREDITS" # custo bruto, antes do crédito de desenvolvedor
  }

  amount {
    specified_amount {
      currency_code = "BRL"
      units         = tostring(var.orcamento_mensal_brl)
    }
  }

  threshold_rules {
    threshold_percent = 0.5
  }
  threshold_rules {
    threshold_percent = 0.9
  }
  threshold_rules {
    threshold_percent = 1.0
  }

  depends_on = [google_project_service.apis]
}
