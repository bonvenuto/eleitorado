# eleitorado

Repositório de dados públicos dos portais de transparência no BigQuery, para monitorar o
governo e as ações públicas. Desenho em `docs/superpowers/specs/`; planos em
`docs/superpowers/plans/`.

## Coletor (onda A)

Fontes declaradas em `fontes/*.yaml`: deputados e CEAP (Câmara), senadores e CEAPS (Senado),
CEIS e CNEP (CGU), municípios (IBGE). Cada coleta guarda o original no GCS
(`originais/…`), carrega o raw no BigQuery (`raw_<órgão>`) e registra tudo em `meta.coletas`.

### Configuração local

1. `uv sync`
2. Copie `.env.exemplo` para `.env` (dev) e `.env.prod` (prod) e ajuste o projeto e o bucket.
   O gcloud deste projeto fica isolado em `.gcloud/` (variável `CLOUDSDK_CONFIG`) e não altera
   outras configurações da máquina.
3. No PowerShell, `. .\scripts\ambiente.ps1` carrega o `.env` para usar `gcloud`, `bq` e
   `terraform`.

### Comandos

```bash
uv run --env-file .env coletor fontes                      # recursos e última coleta
uv run --env-file .env coletor executar                    # coleta o que está vencido
uv run --env-file .env coletor coletar camara.ceap --de 2020
uv run --env-file .env coletor recarregar cgu.ceis --competencia 2026-10-02 --destino replay
```

Use `.env.prod` no lugar de `.env` para gravar em produção, num terminal sem as variáveis de dev
carregadas. A primeira linha do log mostra o ambiente e o projeto em uso.

### Testes

```bash
uv run pytest                                     # unitários
uv run --env-file .env pytest -m integracao       # contra o GCP, só em dev
```

### Infraestrutura

`infra/` (Terraform): bucket `<projeto>-dados` e datasets em `southamerica-east1`.

```powershell
terraform -chdir=infra init "-backend-config=bucket=$($env:ELEITORADO_PROJETO)-tfstate" "-backend-config=prefix=infra"
terraform -chdir=infra apply "-var=projeto=$env:ELEITORADO_PROJETO"
```

## Modelagem (dbt)

- Camadas: `staging` (views sobre o raw), `intermediate` (cota unificada e históricos por eventos)
  e `marts` (dimensões, fatos, alertas e `monitor_fontes`). Em dev, os datasets são
  `dev_<ELEITORADO_USUARIO_DBT>_<camada>`; raw e meta são sempre os de produção.
- Rodar um modelo: `uv run --env-file .env dbt build --project-dir dbt --profiles-dir dbt --target dev --select <modelo>`.
  O projeto inteiro processa cerca de 7,7 GiB; a cota é de 30 GiB por dia.
- LGPD: CPF completo só até `intermediate`. Nos marts, todo CPF sai mascarado (`***.456.789-**`),
  inclusive dentro de nomes; o teste `sem_cpf_completo` roda em todos os marts.
- Reconstruir os históricos a partir dos originais: recarregue cada data no replay
  (`coletor recarregar <recurso> --competencia <data> --destino replay`) e rode
  `dbt build --full-refresh --vars "{fonte_historico: replay}" --select int_cgu__sancoes_eventos+ int_parlamentares__eventos+`.
- Alertas são indícios para investigar, não constatações: a cota reembolsa gastos do parlamentar
  (não é contratação pública) e só aparecem sanções vistas desde a primeira coleta.

## Operação

- **Execução diária:** Cloud Scheduler `pipeline-diario` às 07:30 (Brasília) dispara o Cloud Run Job
  `pipeline`, que roda `coletor pipeline` (coleta + `dbt build`) e grava `meta.execucoes`.
- **Deploy:** cada push em `main` publica a imagem no Artifact Registry e atualiza o job
  (`.github/workflows/deploy.yml`).
- **Vigia:** às 10:00 (Brasília), `.github/workflows/vigia.yml` roda `coletor vigia`; se não houve
  execução agendada com sucesso no dia, o workflow falha e o GitHub avisa por e-mail.
- **Travas de custo:** orçamento de R$ 30/mês com alertas em 50/90/100% (sem créditos), cota de
  30 GiB consultados por dia no BigQuery e `maximum_bytes_billed` de 10 GiB no dbt.
- **Primeiro dia após um deploy feito depois das 07:30:** o vigia das 10:00 reprova porque ainda não
  houve execução agendada da imagem nova; rode o job à mão logo após o deploy.
- **Rodar o job à mão:** `gcloud run jobs execute pipeline --region southamerica-east1 --wait`.
