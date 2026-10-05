# eleitorado

Repositório de dados públicos dos portais de transparência, para monitorar o governo e as ações
públicas. O pipeline roda no GitHub Actions com DuckDB; os dados privados ficam no Cloud Storage
(São Paulo) e os marts são publicados em Parquet no Cloudflare R2. Desenho em
`docs/superpowers/specs/`; planos em `docs/superpowers/plans/`.

## Coletor (onda A)

Fontes declaradas em `fontes/*.yaml`: deputados e CEAP (Câmara), senadores e CEAPS (Senado),
CEIS e CNEP (CGU), municípios (IBGE). Cada coleta guarda o original no GCS (`originais/…`,
imutável), grava o raw em Parquet no lago local (`dados/raw/<órgão>/<recurso>/<partição>/`) e
registra tudo em `dados/meta/`. O lago local espelha `raw/`, `meta/` e `estado/` do bucket.
Onda B1: emendas parlamentares (emendas, convênios, favorecidos e documentos de despesa), contratos do Executivo federal (2013 em diante) e licitações (2013 a abril de 2024), do Portal da Transparência.

### Configuração local

1. `uv sync`
2. Copie `.env.exemplo` para `.env` e ajuste o projeto e o bucket. O gcloud deste projeto fica
   isolado em `.gcloud/` (variável `CLOUDSDK_CONFIG`) e não altera outras configurações da
   máquina.
3. No PowerShell, `. .\scripts\ambiente.ps1` carrega o `.env` para usar `gcloud` e `terraform`.

### Comandos

```bash
uv run --env-file .env coletor estado restaurar            # traz o lago do bucket (dev/)
uv run --env-file .env coletor fontes                      # recursos e última coleta
uv run --env-file .env coletor executar                    # coleta o que está vencido
uv run --env-file .env coletor coletar camara.ceap --de 2020
uv run --env-file .env coletor --target dev pipeline       # coleta + dbt build
uv run --env-file .env coletor estado salvar               # devolve o lago ao bucket
```

Em dev, tudo no bucket fica sob `dev/`. O pipeline de produção só roda no GitHub Actions.

### Testes

```bash
uv run pytest                                     # unitários
uv run --env-file .env pytest -m integracao       # contra o GCS e as fontes, só em dev
```

### Infraestrutura

`infra/` (Terraform): bucket `<projeto>-dados`, contas de serviço e a autenticação do GitHub (WIF).

```powershell
terraform -chdir=infra init "-backend-config=bucket=$($env:ELEITORADO_PROJETO)-tfstate" "-backend-config=prefix=infra"
terraform -chdir=infra apply "-var=projeto=$env:ELEITORADO_PROJETO" "-var=conta_faturamento=<conta>"
```

## Modelagem (dbt)

- DuckDB: `dbt/profiles.yml` tem um arquivo `.duckdb` por target (`dev`, `prod`, `ci`), dentro de
  `ELEITORADO_LAGO`. O arquivo é descartável: os históricos são restaurados de Parquet
  (`estado/historicos/`) antes de cada execução.
- Camadas: `staging` (views sobre o raw em Parquet), `intermediate` (cota unificada e históricos
  por eventos) e `marts` (Parquet em `ELEITORADO_PUBLICO/marts`, o que vai para o bucket público).
- Rodar um modelo: `uv run --env-file .env dbt build --project-dir dbt --profiles-dir dbt --target dev --select <modelo>`
  (crie antes `dados/publico/marts`; o `coletor pipeline` faz isso sozinho).
- LGPD: CPF completo só até `intermediate`. Nos marts, todo CPF sai mascarado (`***.456.789-**`),
  inclusive dentro de nomes; o teste `sem_cpf_completo` roda em todos os marts.
- Históricos (`int_cgu__sancoes_eventos`, `int_parlamentares__eventos`) são permanentes: o raw só
  guarda 60 dias de snapshots, e um `--full-refresh` comum é ignorado nesses modelos. Para
  refazê-los a partir dos originais: `coletor reconstruir` (depois de um `pipeline`).
- CI: o dbt roda sobre `dbt/tests/lago_vazio` (Parquets sem linhas, só com os esquemas). Quando
  uma fonte mudar de colunas, regere com `uv run python scripts/lago_vazio.py dados`.
- Alertas são indícios para investigar, não constatações: a cota reembolsa gastos do parlamentar
  (não é contratação pública) e só aparecem sanções vistas desde a primeira coleta.

## Operação

- **Execução diária:** `.github/workflows/pipeline.yml`, às 07:30 (Brasília): restaura o lago (cache
  do Actions ou bucket), coleta, roda o `dbt build`, salva o estado no bucket e publica marts e
  linhagem no R2. Uma falha em qualquer passo gera e-mail do GitHub.
- **Primeira carga:** dispare o workflow à mão com `reconstruir` marcado.
- **Público:** `manifesto.json`, `marts/` e `linhagem/index.html` no bucket R2, em
  <https://pub-e140b10136c94c9eb7cdb0a31fe603f3.r2.dev> (endereço `r2.dev`, até haver domínio próprio). Os arquivos são
  enviados antes do manifesto; quem lê o manifesto sempre vê um conjunto completo.
- **Recuperação:** objetos sobrescritos ou apagados no bucket privado ficam 30 dias na exclusão
  reversível; `coletor reconstruir` refaz os históricos a partir dos originais.
- **Paralelo da migração:** enquanto o Cloud Run antigo roda (imagem congelada), o workflow grava
  sob `paralelo/` e roda `coletor reconciliar`, que falha se os marts divergirem do BigQuery.

### Cloudflare R2 (configuração única)

1. No painel da Cloudflare, crie o bucket `eleitorado-publico` e ative o acesso público pelo
   endereço `r2.dev` (até haver um domínio próprio).
2. Crie um token de API do R2 com permissão "Object Read & Write" só nesse bucket.
3. No GitHub: secrets `R2_CONTA` (id da conta), `R2_CHAVE_ID` e `R2_SEGREDO`; variável
   `R2_BUCKET=eleitorado-publico`. Use `gh secret set <nome>`, que lê o valor sem ecoar.
