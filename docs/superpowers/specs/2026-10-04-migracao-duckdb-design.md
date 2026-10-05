# Migração do pipeline para DuckDB e publicação em Parquet

**Data:** 2026-10-04
**Status:** aprovado em conversa, aguardando revisão da spec escrita
**Substitui:** as seções 5, 6.3 a 6.6, 7.1 e 8 da [spec da onda A](2026-10-03-ingestao-onda-a-design.md), nas partes que tratam de BigQuery, Cloud Run, Artifact Registry e do vigia. As regras de coleta (seção 6), de modelagem (seção 7) e de LGPD (seção 7.6) continuam valendo, salvo onde esta spec diz o contrário.

## 1. Objetivo

Tirar o pipeline (coletor e dbt) do BigQuery e do Cloud Run e rodá-lo no GitHub Actions com DuckDB. Os marts passam a ser publicados como Parquet num bucket público do Cloudflare R2, junto com o site de linhagem (`dbt docs`).

O motivo é custo. O pipeline atual já quase não custa nada, mas uma web app pública que consultasse o BigQuery pagaria a cada acesso. Com Parquet num bucket sem custo de saída, lido no navegador pelo DuckDB-WASM, servir os dados custa praticamente zero, seja qual for o número de visitantes.

**Fica fora desta spec:** a web app, que terá a sua própria spec. Também fica fora o domínio próprio: por enquanto, o endereço público é o `r2.dev`, e a troca para um domínio gerenciado pela Cloudflare é um passo de configuração anterior ao lançamento da web app.

**Critérios de sucesso:**
- o workflow diário roda sem BigQuery nem Cloud Run e termina com o `dbt build` sem erros;
- os marts e a linhagem ficam acessíveis por HTTPS no R2;
- durante 7 dias seguidos, a reconciliação com o pipeline atual não acusa divergência (seção 8);
- depois da virada, sobra no GCP só o bucket privado, a WIF, a conta `pipeline` e o orçamento;
- o custo mensal fica abaixo de R$ 1 no GCS, e R2 e GitHub Actions ficam dentro das faixas gratuitas.

## 2. Decisões

| Tema | Decisão | Motivo |
|---|---|---|
| Onde roda | GitHub Actions, workflow agendado | sem infraestrutura de execução; gratuito enquanto couber nos 2.000 min/mês de um repositório privado (o pipeline usa cerca de 300 min/mês) e ilimitado quando o repositório ficar público |
| Dados privados | o bucket GCS atual, em São Paulo, com acesso por WIF | sem chave guardada no GitHub; os originais já estão lá; os dados continuam no Brasil |
| Dados públicos | Cloudflare R2, com token restrito ao bucket público | 10 GB grátis e sem custo de saída |
| Estado | raw em Parquet imutável; DuckDB como arquivo de trabalho descartável; históricos exportados para Parquet | backup pequeno e incremental, sem ponto único de falha, e o raw legível por qualquer ferramenta |
| Cache | cache do GitHub Actions para o arquivo `.duckdb` e o espelho local do raw; GCS como fonte da verdade | evita baixar o raw inteiro do GCS todo dia (saída para a internet custa cerca de US$ 0,12 a 0,19 por GB) |
| Histórico | reconstruído a partir dos originais, sem exportar o BigQuery | todos os originais desde a primeira coleta estão no GCS; a reconstrução serve também de teste |
| Virada | uma semana em paralelo com reconciliação diária e depois o desligamento | diferenças que só aparecem com dados de dias seguintes também são pegas |
| dbt | projeto só DuckDB; sem macros com uma versão para cada banco | o pipeline antigo fica congelado na imagem atual durante o paralelo |

## 3. Arquitetura

```
GitHub Actions (pipeline.yml, 07:30 Brasília)
  1. restaurar estado ── cache do Actions  ou  GCS (raw/, meta/, estado/historicos/)
  2. autenticar ──────── GCP por WIF (conta pipeline, só GCS); R2 por token (secret)
  3. coletar ─────────── fontes → originais/ (GCS) → Parquet em dados/raw/ (local)
  4. transformar ─────── dbt build (DuckDB): staging → intermediate → marts (Parquet)
  5. salvar estado ───── GCS: Parquets novos do raw, meta, históricos (+ cópia diária)
  6. publicar ────────── R2: marts/ e linhagem/  (só se o passo 4 terminou sem erro)
  7. avisar ──────────── falha do workflow = e-mail do GitHub
```

O CI dos PRs (`ci.yml`) roda os testes Python e os testes unitários do dbt num DuckDB em memória, sem credencial nenhuma.

## 4. Armazenamento

### 4.1 GCS privado (`dados-publicos-prd-dados`)

```
<prefixo>originais/<órgão>/<recurso>/...                 imutável; vai para Archive após 30 dias
<prefixo>raw/<órgão>/<recurso>/<competência>/<coleta_id>.parquet
<prefixo>meta/coletas/<data>/<coleta_id>.parquet
<prefixo>meta/execucoes/<data>/<execucao_id>.parquet
<prefixo>estado/historicos/<modelo>.parquet              versão atual dos eventos
<prefixo>estado/historicos/<modelo>/<data>.parquet       cópia diária, apagada após 30 dias
```

- **Prefixo:** `ELEITORADO_PREFIXO`. Durante o paralelo é `paralelo/`; depois da virada fica vazio.
- **Originais:** continuam com `if_generation_match=0`, sem apagar nem sobrescrever. No paralelo, o pipeline novo **lê** os `originais/` do pipeline antigo, mas grava os seus em `paralelo/originais/`.
- **Raw:** a mesma regra de hoje:
  - snapshots (CGU diária; deputados e senadores semanais): um arquivo por data de referência, apagado após 60 dias;
  - recursos por competência (CEAP e CEAPS por ano): um arquivo por competência, substituído quando a fonte muda. O arquivo anterior fica 30 dias com o sufixo `.substituido-<data>`.
- **Retenção:** aplicada por regras de ciclo de vida do bucket, gerenciadas no Terraform, e não pelo código.

### 4.2 R2 público (`eleitorado-publico`)

```
marts/<mart>.parquet
marts/fct_despesa_cota_parlamentar/casa=<casa>/ano=<ano>/data_0.parquet
linhagem/index.html, manifest.json, catalog.json
manifesto.json        {gerado_em, versao, arquivos: [{caminho, linhas, bytes, sha256}]}
```

- O `coletor publicar` só envia arquivos sob `marts/` e `linhagem/`, além do `manifesto.json`. Qualquer outro caminho faz o comando falhar.
- A publicação substitui o conteúdo e apaga os arquivos que deixaram de existir. O `manifesto.json` é enviado por último. Assim, quem lê o manifesto vê sempre um conjunto completo de arquivos.
- O bucket é criado à mão no painel da Cloudflare, e o passo a passo vai no README. O token de API é restrito a "Object Read & Write" desse bucket.

### 4.3 Cache do GitHub Actions

- **Conteúdo:** `dados/eleitorado.duckdb` e o espelho `dados/raw/` e `dados/meta/`.
- **Chave:** `estado-<run_id>`, restaurando pela chave mais recente com prefixo `estado-`.
- **Sem cache, ou com cache incompleto:** o `coletor estado restaurar` baixa do GCS o que faltar. Para isso, compara a lista de objetos do GCS com o espelho local e baixa só a diferença.

## 5. Credenciais e permissões

| Quem | Acesso | Como |
|---|---|---|
| `pipeline.yml` (só a partir de `refs/heads/main`) | GCS: ler; criar objetos; apagar só em `raw/`, `meta/` e `estado/` (e em `paralelo/`) | WIF + conta `pipeline` (impersonação) |
| `pipeline.yml` | R2: escrever no bucket público | secrets `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` |
| `pipeline.yml` (só no paralelo) | BigQuery: ler `marts` e `meta` | conta `pipeline`; a permissão sai na virada |
| `ci.yml` | nenhum | — |
| Internet | ler o R2 público | acesso público do bucket (`r2.dev`) |

- A permissão de apagar em prefixos específicos usa uma condição do IAM sobre o nome do objeto (`resource.name.startsWith(...)`).
- O `workflow_dispatch` do `pipeline.yml` também só autentica a partir da `main`.
- O workflow tem `concurrency: pipeline`, sem cancelar a execução em andamento, para que duas execuções nunca escrevam no estado ao mesmo tempo.

## 6. Coletor

- **Mantidos:** `conversao.py`, `adaptadores/*`, `agenda.py`, `competencias.py`, `hashes.py`, `http.py`, `cgu.py`, `manifesto.py` e `nomes.py`.
- **`armazenamento.py`:** passa a aceitar o prefixo configurável.
- **`warehouse.py`:** sai.
- **Novo `lago.py`:**
  - grava o Parquet da coleta em `dados/raw/<órgão>/<recurso>/<competência>/<coleta_id>.parquet`;
  - aplica a regra de substituição por competência;
  - mantém a lista de arquivos novos e substituídos para o `estado salvar`.
- **`meta.py`:**
  - `coletas` e `execucoes` passam a ser gravadas em Parquet, um arquivo por registro;
  - as consultas de deduplicação por `sha256`, último sucesso e agenda passam a ser SQL no DuckDB sobre `dados/meta/`;
  - `fontes` é gravada a cada execução, a partir do manifesto, em `dados/meta/fontes.parquet`, com `recurso_id` e `cadencia_corrente`. É a entrada do `monitor_fontes`;
  - os status continuam os mesmos.
- **Novo `estado.py`:**
  - `restaurar()`: completa o espelho local a partir do GCS. Se o `.duckdb` não existir, recria as tabelas dos históricos a partir de `estado/historicos/*.parquet`;
  - `salvar()`: envia ao GCS os arquivos novos e substituídos, exporta os históricos e faz a cópia diária;
  - `publicar()`: envia `dados/publico/` ao R2, com a lista de caminhos permitidos (seção 4.2).
- **`dbt.py`:** o mesmo `dbt build` (sem testes unitários) no target `prod` do DuckDB.
- **Comandos da CLI:**
  - `estado restaurar`, `pipeline`, `estado salvar` e `publicar`;
  - `reconstruir`: recria o raw de todas as datas a partir dos originais num diretório de replay local e roda o dbt com `fonte_historico: replay` e `--full-refresh` nos históricos. Serve para a primeira carga, para a virada e para recuperar o histórico;
  - `reconciliar`: só no paralelo (seção 8);
  - `fontes`, `coletar` e `executar` continuam;
  - `vigia` e `recarregar` saem; o papel do `recarregar` passa ao `reconstruir`.
- **Dependências:**
  - saem `google-cloud-bigquery` e `dbt-bigquery`;
  - entram `duckdb`, `dbt-duckdb` e `boto3`;
  - `google-cloud-bigquery` fica num grupo opcional `migracao` até a virada.

## 7. Projeto dbt

- **Profile:** `prod` (`dados/eleitorado.duckdb`), `dev` (`dados/dev.duckdb`) e `ci` (`:memory:`). O target `prod` usa `threads: 4` e `memory_limit` de 4 GB (o runner tem 7 GB).
- **Sources:** externos, lendo `{{ env_var('ELEITORADO_LAGO') }}/raw/<órgão>/<recurso>/*/*.parquet` e `.../meta/...`. Com `fonte_historico: replay`, os snapshots vêm do diretório de replay local.
- **Tradução:** as funções do BigQuery viram as equivalentes do DuckDB, concentradas nas macros sempre que possível:
  - `safe_cast` → `try_cast`;
  - `json_value` → `json_extract_string`;
  - `regexp_contains` → `regexp_matches`;
  - `to_hex(md5())` → `md5()`;
  - `array_agg(...)[offset(0)]` → `arg_max`;
  - dígito verificador com `list_transform`/`list_sum`.

  Configurações `partition_by`/`cluster_by` saem.
- **Materializações:**
  - staging: views;
  - intermediate: tabelas;
  - `int_cgu__sancoes_eventos` e `int_parlamentares__eventos`: incrementais com `delete+insert` por `evento_id`, mantendo o `particao` por cadastro e por casa e a proteção contra `--full-refresh` fora do replay;
  - marts: `external`, em Parquet sob `dados/publico/marts/`. O fato da cota fica particionado por `casa` e `ano`.
- **Ids:** os ids das despesas da Câmara mudam, porque o `hash_linha` é calculado de outro jeito. Não há consumidores ainda.
- **Linhagem:** `dbt docs generate` gera o site estático, copiado para `dados/publico/linhagem/`.
- **Testes:** os mesmos da spec original (seção 7.7) e do Plano 3, traduzidos. O `monitor_fontes` passa a ler o `meta` em Parquet, e os testes de atraso continuam valendo:
  - se o de erro falhar, o workflow falha e nada é publicado nesse dia;
  - o workflow não tem nova tentativa automática, então não há custo de build repetido.

## 8. Paralelo, reconciliação e virada

### 8.1 Paralelo

- O `deploy.yml` é desligado no primeiro PR da migração. O Cloud Run Job continua rodando a imagem `2acac63`, com o Scheduler e o vigia como estão.
- O pipeline novo roda com `ELEITORADO_PREFIXO=paralelo/`. A primeira carga é um disparo manual de `coletor reconstruir`.

### 8.2 Reconciliação (`coletor reconciliar`)

Depois do `dbt build`, o comando compara o DuckDB com os marts do BigQuery:

| Comparação | Regra |
|---|---|
| Linhas e soma de `valor_reembolsado` por casa e ano | iguais (tolerância de R$ 0,01 na soma) |
| Linhas por casa e `fornecedor_tipo_documento` | iguais |
| `sancao_id` presentes em `fct_sancao`; eventos por tipo no histórico | iguais |
| Alertas de sancionado, por (`sancao_id`, casa, `data_emissao`, `fornecedor_documento`, `valor_reembolsado`) | mesmo conjunto |
| Linhas de `alerta_cota_documento_invalido`, `dim_*` | iguais |

- Uma divergência faz o workflow falhar e lista as diferenças.
- Uma diferença de horário entre os dois pipelines também conta como divergência. Ela é analisada caso a caso, e a tolerância não é ajustada.
- As consultas ao BigQuery são agregadas e baratas.

### 8.3 Critério e passos da virada

**Critério:** 7 execuções diárias seguidas sem divergência, com pelo menos uma coleta semanal de deputados e senadores no meio.

**Passos, em ordem:**
1. Rodar `coletor reconstruir` com o prefixo vazio, recriando raw e históricos na raiz.
2. Rodar o pipeline um dia com o prefixo vazio e conferir.
3. No Terraform, remover:
   - Cloud Run Job, Cloud Scheduler e Artifact Registry;
   - as contas `deployer` e `ci-github`, com as permissões delas;
   - os datasets do BigQuery (`meta`, `raw_*`, `replay`, os `_dev`, `staging`, `intermediate`, `marts` e `ci`);
   - o acesso da conta `pipeline` ao BigQuery.
4. Remover os workflows `deploy.yml` e `vigia.yml`, o `Dockerfile`, o comando `reconciliar` e o grupo `migracao`.
5. Voltar a cota diária do BigQuery ao padrão, ou desativar a API do BigQuery.
6. Apagar `paralelo/` no bucket.

## 9. Testes

- **Python:** os testes de hoje, adaptados. `warehouse` dá lugar a `lago`, e o `meta` passa a ser em Parquet. Testes novos para:
  - `estado.restaurar` (cache completo, cache vazio, cache parcial);
  - `estado.salvar` (só arquivos novos, cópia diária);
  - `publicar` (lista de caminhos permitidos, manifesto por último, remoção de arquivos que deixaram de existir);
  - `reconstruir`.

  O GCS e o R2 são falsos nos testes unitários, como no Plano 1.
- **dbt:** todos os testes de dados e unitários do Plano 3, traduzidos, mais um teste unitário dos sources externos com `fonte_historico: replay`.
- **Integração (manual, marcador `integracao`):**
  - restaurar a partir do GCS de verdade num diretório vazio;
  - publicar num bucket R2 de teste.
- **Reconciliação:** a seção 8.2 é o teste de aceitação da migração.

## 10. Divisão em planos

1. **Plano 4, migração e paralelo:** seções 4 a 7, a 8.1 e a 8.2, com a primeira carga e a semana de reconciliação.
2. **Plano 5, virada e limpeza:** seção 8.3, executada só depois do critério de virada.

## 11. Riscos

| Risco | Mitigação |
|---|---|
| O cache some e o restaurar baixa tudo do GCS | é raro (7 dias sem uso ou limpeza manual); custa centavos por vez |
| O runner do GitHub fica sem memória no fato da cota | `memory_limit` no profile; o DuckDB usa disco quando passa do limite; o volume atual (5,6 milhões de linhas) cabe com folga |
| Token do R2 vaza | só dá escrita no bucket público, sem CPF; o pipeline republica no dia seguinte; troca do token pelo painel |
| Publicação parcial | o manifesto vai por último; a web app lê pelo manifesto |
| Bug no incremental corrompe o histórico | cópia diária de 30 dias em `estado/historicos/<modelo>/` e `reconstruir` a partir dos originais |
| Endereço `r2.dev` com limite de requisições | só serve enquanto não houver tráfego; a troca para domínio próprio é pré-requisito da web app |
