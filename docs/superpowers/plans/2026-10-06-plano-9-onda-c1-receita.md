# Plano 9: onda C1, cadastro de empresas da Receita Federal

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** trazer o cadastro da Receita (situação, abertura, CNAE, porte, Simples/MEI e sócios) das
empresas que aparecem nos dados do eleitorado, publicar `dim_empresa` e `dim_estabelecimento` e
quatro alertas novos, sem expor endereço, contato nem sócio pessoa física.

**Architecture:** um adaptador novo do coletor (`webdav_zip`) baixa a base mensal do CNPJ do
WebDAV da Receita com retomada por `Range`, recorta em fluxo só as raízes de interesse (que o dbt
grava em `<lago>/rfb_raizes_interesse.parquet`) e carrega o recorte no raw, numa partição mensal
sem expiração. Outro adaptador (`api_detalhe`) traz nome civil e CPF dos deputados. Esses recursos
têm `grupo: receita` e rodam num workflow próprio (`receita.yml`, toda segunda); o pipeline diário
só coleta o grupo `diario`, mas roda o dbt de tudo e publica os marts.

**Tech Stack:** Python 3.12, uv, httpx (PROPFIND e `Range`), DuckDB 1.5.6, pyarrow, pydantic 2,
dbt-duckdb 1.11, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-06-onda-c1-receita-cnpj-design.md` (a seção 10 traz o
protótipo; as seções 3, 5 e 7 já incorporam o que a implementação mostrou).

## Como este plano é executado

Todo o código foi escrito e validado no branch local **`proto/onda-c1`** (a partir de `40120b0`,
a `main` atual):

- testes unitários do coletor e do agente, e o dbt inteiro (`dbt build`) sobre o lago vazio do CI;
- smoke tests contra as fontes reais: o adaptador `webdav_zip` baixou `Cnaes` e `Simples` (308 MB,
  50,4 milhões de linhas lidas, 159.215 mantidas, 141 s) do WebDAV da Receita e converteu para
  Parquet pelo caminho normal do coletor; o `api_detalhe` trouxe os 648 deputados da 57ª
  legislatura da API da Câmara, todos com CPF e nome civil;
- o dbt dos modelos novos sobre os dados reais: um lago de validação com o recorte completo da
  competência 2026-09 (250.810 empresas, 657.506 estabelecimentos, 388.285 sócios) e uma cópia do
  banco do agente. Os quatro alertas deram os números da seção 10 da spec, e os testes de dados
  (`unique`, `not_null`, `sem_cpf_completo`, `sem_dados_pessoais`) passaram.

O conteúdo de cada arquivo é o do **último commit** de `proto/onda-c1`; o plano não o repete.
Cada tarefa:

1. traz os arquivos da tarefa com `git checkout proto/onda-c1 -- <arquivos>`;
2. roda os testes da tarefa e confere o resultado esperado;
3. faz a **prova de mutação** indicada (estraga de propósito uma regra, vê o teste falhar,
   restaura com `git checkout -- <arquivo>` e vê passar de novo). Todas as mutações deste plano
   foram executadas no protótipo e falham como descrito;
4. roda `uv run ruff check .`, `uv run ruff format --check .` e `uv run pytest -q`;
5. faz o commit com a mensagem indicada.

Os arquivos de cada tarefa só usam o que tarefas anteriores trouxeram, então cada commit fica
verde sozinho.

### Verificação dbt (lago vazio)

Usada nas tarefas 5 a 9. Gera o lago vazio do CI a partir de `esquemas.json` e roda o dbt inteiro
(modelos, testes de dados e unitários), como o job `testes` do CI. Em PowerShell:

```powershell
$env:ELEITORADO_LAGO = "dbt/tests/lago_vazio"
$env:ELEITORADO_PUBLICO = "$env:TEMP\publico-ci"
uv run python scripts/lago_vazio.py
New-Item -ItemType Directory -Force "$env:ELEITORADO_PUBLICO\marts" | Out-Null
uv run dbt build --project-dir dbt --profiles-dir dbt --target ci
Remove-Item Env:ELEITORADO_LAGO, Env:ELEITORADO_PUBLICO
```

Esperado: a última linha `Done. PASS=<n> WARN=0 ERROR=0 SKIP=0 ...` (sem `ERROR` nem `FAIL`). Ao
fim do plano, `PASS=203`.

## Global Constraints

- Branch de trabalho: `feat/onda-c1-receita`, criado a partir da `main` atual. Nunca commitar em
  `main` (protegida: só por PR com o check `testes`).
- Os marts públicos nunca têm endereço (logradouro, número, complemento, bairro, CEP), contato
  (telefone, e-mail) nem sócio pessoa física (nome, documento); CPF nunca completo (testes
  `sem_dados_pessoais` e `sem_cpf_completo`).
- Sócios, endereço e contato ficam só em `intermediate` (lago privado). O CPF completo dos
  deputados fica só no raw e em `stg_camara__deputados_detalhe`.
- O pipeline diário nunca coleta a Receita: os recursos `rfb.*` e `camara.deputados_detalhe` têm
  `grupo: receita`; `coletor executar` e `coletor pipeline` usam `--grupo diario` por padrão.
- Os ZIPs da Receita (7,6 GB por mês) não são arquivados: arquiva-se o recorte, e o registro da
  coleta guarda nome, tamanho, SHA-256, linhas lidas e mantidas de cada ZIP.
- Hosts só `.gov.br` e `.leg.br` (o cliente HTTP já recusa outros).
- Linhas de até 100 colunas (`ruff`), código e textos em português.
- Toda mensagem de commit termina com:
  ```
  Co-Authored-By: Gemini <noreply@google.com>
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  ```

## Review Focus

1. **A Receita muda o layout ou o link:** número de colunas diferente falha com mensagem clara e
   nada parcial é gravado; pasta `AAAA-MM` ausente diz "o link mudou?"
   (`test_adaptador_webdav_zip.py::test_numero_de_colunas_diferente_do_layout_falha`,
   `::test_sem_pasta_de_competencia_falha_com_mensagem_clara`).
2. **Download que cai no meio ou servidor que ignora o `Range`:** retoma de onde parou; um 200 na
   retomada vira erro em vez de corromper o arquivo; 404 não é repetido
   (`test_http.py::test_baixar_retomando_*`).
3. **O pipeline diário baixando 7,6 GB por engano:** o grupo padrão é `diario`
   (`test_cli.py::test_executar_sem_recursos_so_coleta_o_grupo_pedido`,
   `test_manifesto.py::test_recursos_da_receita_ficam_fora_do_pipeline_diario`).
4. **Dado pessoal num mart público** (coluna de endereço ou de sócio, CPF na razão social do MEI):
   `sem_dados_pessoais` e `sem_cpf_completo` em todos os marts novos.
5. **Antes da primeira coleta da Receita** (raw sem `rfb`): o pipeline diário e o `preparar` do
   agente criam Parquet vazio com o esquema e o dbt não falha
   (`test_preparar.py::test_preparar_cria_parquet_vazio_para_fonte_ainda_sem_coleta`; o lago vazio
   do CI cobre o pipeline).

## Rulings da implementação (em relação à spec)

Já incorporados à spec: um grupo é uma coleta (não um ZIP), com retomada por download; partição
`raw/rfb/<recurso>/<AAAAMM>/`; raízes em `<lago>/rfb_raizes_interesse.parquet` (o dbt-duckdb não
cria pasta para Parquet externo); o sócio empresa vem só com a raiz do CNPJ, então o alerta 3 casa
por ela; o alerta 3 tem uma linha por licitação e par; `sem_dados_pessoais` é genérico (um teste
singular sobre o `information_schema` rodava antes dos marts e não pegava a coluna); o `preparar`
do agente cria Parquet vazio para fonte sem coleta.

---

### Tarefa 1: Manifesto, fontes da Receita e grupo de recursos

**Files:**
- Create: `fontes/rfb.yaml`
- Modify: `coletor/manifesto.py` (modelo `Recorte`; campos `grupo`, `recorte`, `url_detalhe`;
  adaptadores `webdav_zip` e `api_detalhe`; validações), `coletor/cli.py` (`--grupo` em
  `executar` e `pipeline`), `fontes/camara.yaml` (`deputados_detalhe`), `tests/amostras.py`
  (`RAIZ_WEBDAV`, `propfind_webdav`, `recurso_webdav`), `tests/test_manifesto.py`,
  `tests/test_cli.py`

**Interfaces:**
- Produces: `Recorte(arquivos: str, colunas: list[str], raizes: str | None)`;
  `Recurso.grupo: Literal["diario", "receita"] = "diario"`, `Recurso.recorte: Recorte | None`,
  `Recurso.url_detalhe: str | None`; `cli.GRUPOS = ("diario", "receita")`.
- Produces (testes): `tests.amostras.RAIZ_WEBDAV`, `propfind_webdav(pasta, itens) -> str`,
  `recurso_webdav(raizes="rfb/raizes.parquet", arquivos="Empresas*.zip") -> Recurso`.

- [ ] **Passo 1:** `git checkout main; git pull; git checkout -b feat/onda-c1-receita`.
- [ ] **Passo 2:** `git checkout proto/onda-c1 -- coletor/manifesto.py coletor/cli.py fontes/rfb.yaml fontes/camara.yaml tests/amostras.py tests/test_manifesto.py tests/test_cli.py`.
- [ ] **Passo 3:** `uv run pytest -q tests/test_manifesto.py tests/test_cli.py`. Esperado:
  **22 passed**.
- [ ] **Passo 4 (mutação):** em `coletor/cli.py`, na função `_recursos`, troque
  `return [rc for rc in manifesto.todos() if rc.recurso.grupo == args.grupo]` por
  `return manifesto.todos()`. `test_executar_sem_recursos_so_coleta_o_grupo_pedido` **deve
  falhar**. Restaure com `git checkout -- coletor/cli.py` e confirme 22 passed.
- [ ] **Passo 5:** ruff e pytest completos verdes (**278 passed**). Commit:
  `feat(coletor): manifesto da Receita e grupo de recursos fora do pipeline diário`.

### Tarefa 2: Cliente HTTP com listagem WebDAV e download com retomada

**Files:**
- Modify: `coletor/http.py` (`ItemWebdav`, `ClienteHttp.baixar_retomando`,
  `ClienteHttp.listar_webdav`, `_itens_webdav`), `tests/test_http.py`

**Interfaces:**
- Produces: `ClienteHttp.baixar_retomando(url, destino, usuario=None, tentativas=20) -> Download`
  (retoma com `Range: bytes=<recebido>-`, exige 206 na retomada, repete falha de transporte e
  5xx/429 com espera crescente, não repete 4xx); `ClienteHttp.listar_webdav(url, usuario) ->
  list[ItemWebdav]`; `ItemWebdav(nome: str, pasta: bool, tamanho: int | None)`.

- [ ] **Passo 1:** `git checkout proto/onda-c1 -- coletor/http.py tests/test_http.py`.
- [ ] **Passo 2:** `uv run pytest -q tests/test_http.py`. Esperado: **16 passed**.
- [ ] **Passo 3 (mutação):** em `coletor/http.py`, troque `if recebido and r.status_code != 206:`
  por `if False:`. `test_baixar_retomando_recusa_servidor_que_ignora_o_range` **deve falhar**.
  Restaure e confirme.
- [ ] **Passo 4:** ruff e pytest completos verdes (**283 passed**). Commit:
  `feat(coletor): listagem WebDAV e download com retomada por Range`.

### Tarefa 3: Adaptadores `webdav_zip` e `api_detalhe`

**Files:**
- Create: `coletor/adaptadores/webdav_zip.py`, `coletor/adaptadores/api_detalhe.py`,
  `tests/test_adaptador_webdav_zip.py`, `tests/test_adaptador_api_detalhe.py`
- Modify: `coletor/adaptadores/__init__.py` (registra os dois)

**Interfaces:**
- Consumes: Tarefas 1 e 2.
- Produces (`webdav_zip`): `competencia_disponivel(recurso, http) -> Competencia` (pasta
  `AAAA-MM` mais recente), `caminho_raizes(relativo) -> Path` (relativo a `ELEITORADO_LAGO`),
  `carregar_raizes(caminho) -> frozenset[bytes]`, `registros(fluxo) -> Iterator[bytes]`,
  `recortar(fluxo, saida, raizes, colunas, nome) -> tuple[int, int]` (lidos, mantidos),
  `extrair(...) -> Extracao` (o original é o recorte `recorte.csv`; `parametros["arquivos"]` com
  nome, bytes, sha256, linhas_lidas e linhas_mantidas de cada ZIP), `preparar(...) -> Preparado`.
- Produces (`api_detalhe`): `extrair(...)` (lista os ids pelo `api_json` e busca
  `url_detalhe` de cada um, sem repetir) e `preparar(...)` (o do `api_json`).

- [ ] **Passo 1:** `git checkout proto/onda-c1 -- coletor/adaptadores/webdav_zip.py coletor/adaptadores/api_detalhe.py coletor/adaptadores/__init__.py tests/test_adaptador_webdav_zip.py tests/test_adaptador_api_detalhe.py`.
- [ ] **Passo 2:** `uv run pytest -q tests/test_adaptador_webdav_zip.py tests/test_adaptador_api_detalhe.py`.
  Esperado: **11 passed**.
- [ ] **Passo 3 (mutação 1):** em `coletor/adaptadores/webdav_zip.py`, troque
  `registro[1:9] in raizes` por `registro[0:8] in raizes`.
  `test_recorte_mantem_as_raizes_le_latin1_e_tira_nul` **deve falhar**. Restaure.
- [ ] **Passo 4 (mutação 2):** no mesmo arquivo, troque
  `if pendente.count(b'"') % 2 == 0:` por `if True:`.
  `test_registro_com_quebra_de_linha_entre_aspas_continua` **deve falhar**. Restaure.
- [ ] **Passo 5 (mutação 3):** em `coletor/adaptadores/api_detalhe.py`, troque
  `url_detalhe.replace("{id}", id_)` por `url_detalhe.replace("{x}", id_)`.
  `test_busca_o_detalhe_de_cada_id_da_lista_sem_repetir` **deve falhar**. Restaure e confirme 11
  passed.
- [ ] **Passo 6:** ruff e pytest completos verdes (**294 passed**). Commit:
  `feat(coletor): adaptadores webdav_zip (recorte em fluxo da base do CNPJ) e api_detalhe`.

### Tarefa 4: Coleta pula a competência já coletada e guarda o recorte sem expirar

**Files:**
- Modify: `coletor/coleta.py` (`particionamento`: `webdav_zip` vai para partição mensal sem
  expiração; `coletar`: adaptador com `competencia_disponivel` descobre a competência antes de
  baixar e, se ela já foi coletada, termina como `sem_alteracao` com o SHA anterior),
  `tests/test_coleta.py`

**Interfaces:**
- Consumes: Tarefa 3 (`webdav_zip.competencia_disponivel`).
- Produces: comportamento novo de `coletar` para qualquer adaptador que exponha
  `competencia_disponivel(recurso, http) -> Competencia`.

- [ ] **Passo 1:** `git checkout proto/onda-c1 -- coletor/coleta.py tests/test_coleta.py`.
- [ ] **Passo 2:** `uv run pytest -q tests/test_coleta.py`. Esperado: **17 passed**.
- [ ] **Passo 3 (mutação 1):** em `coletor/coleta.py`, troque
  `registro.sha256_conteudo = anterior` por `pass`.
  `test_competencia_da_receita_ja_coletada_nao_e_baixada` **deve falhar** (sem o SHA, a semana
  seguinte baixaria tudo de novo). Restaure.
- [ ] **Passo 4 (mutação 2):** troque `return Particionamento("MONTH")` por
  `return Particionamento("DAY", 60)`.
  `test_recorte_da_receita_carrega_na_particao_mensal_sem_expirar` **deve falhar**. Restaure e
  confirme 17 passed.
- [ ] **Passo 5:** ruff e pytest completos verdes (**296 passed**). Commit:
  `feat(coletor): competência da Receita já coletada não é baixada de novo; recorte sem expirar`.

### Tarefa 5: Fontes e staging da Receita no dbt

**Files:**
- Create: `dbt/models/staging/stg_rfb__empresas.sql`, `stg_rfb__estabelecimentos.sql`,
  `stg_rfb__socios.sql`, `stg_rfb__simples.sql`, `stg_rfb__codigos.sql`,
  `stg_camara__deputados_detalhe.sql` (todos em `dbt/models/staging/`)
- Modify: `dbt/models/staging/fontes.yml` (fonte `raw_rfb` e tabela `deputados_detalhe`),
  `dbt/macros/conversoes.sql` (`data_rfb`, `numero_rfb`), `dbt/tests/lago_vazio/esquemas.json`
  (esquemas das 11 tabelas novas)

**Interfaces:**
- Produces: views `stg_rfb__empresas` (`cnpj_raiz, razao_social, natureza_juridica_codigo,
  qualificacao_responsavel_codigo, capital_social, porte_codigo, ente_federativo_responsavel,
  competencia`), `stg_rfb__estabelecimentos` (`cnpj_raiz, cnpj, matriz, nome_fantasia,
  situacao_codigo, data_situacao, motivo_codigo, data_inicio_atividade, cnae_principal,
  uf_sigla, municipio_rfb_codigo`, endereço e contato, `competencia`), `stg_rfb__socios`
  (`cnpj_raiz, tipo_socio_codigo, nome_socio, documento_socio, qualificacao_codigo,
  data_entrada, ...`), `stg_rfb__simples`, `stg_rfb__codigos (tabela, competencia, codigo,
  descricao)`, `stg_camara__deputados_detalhe (id_deputado, nome_civil, cpf, data_referencia)`.

- [ ] **Passo 1:** `git checkout proto/onda-c1 -- dbt/models/staging/stg_rfb__empresas.sql dbt/models/staging/stg_rfb__estabelecimentos.sql dbt/models/staging/stg_rfb__socios.sql dbt/models/staging/stg_rfb__simples.sql dbt/models/staging/stg_rfb__codigos.sql dbt/models/staging/stg_camara__deputados_detalhe.sql dbt/models/staging/fontes.yml dbt/macros/conversoes.sql dbt/tests/lago_vazio/esquemas.json`.
- [ ] **Passo 2:** rode a **Verificação dbt (lago vazio)**. Esperado: sem `ERROR` nem `FAIL`.
- [ ] **Passo 3 (mutação):** apague a pasta `dbt/tests/lago_vazio/raw/rfb/socios` (o Parquet vazio
  que o `esquemas.json` gera) e rode só
  `uv run dbt build --project-dir dbt --profiles-dir dbt --target ci --select stg_rfb__socios`
  com as mesmas variáveis da verificação: **deve dar ERROR** `No files found`. Rode
  `uv run python scripts/lago_vazio.py` (recria a pasta) e o mesmo comando: `PASS=1`.
- [ ] **Passo 4:** ruff e pytest completos verdes. Commit:
  `feat(dbt): fontes e staging da base do CNPJ e do detalhe de deputados`.

### Tarefa 6: Intermediários da Receita e as raízes de interesse

**Files:**
- Create: `dbt/models/intermediate/int_rfb__raizes_interesse.sql` (Parquet externo em
  `<ELEITORADO_LAGO>/rfb_raizes_interesse.parquet`), `int_rfb__municipios.sql`,
  `int_rfb__estabelecimentos.sql`, `int_rfb__socios.sql`, `int_rfb__empresas.sql`,
  `dbt/models/intermediate/rfb.yml` (teste unitário da data de abertura)

**Interfaces:**
- Consumes: Tarefa 5.
- Produces: `int_rfb__raizes_interesse (raiz, origens)`; `int_rfb__municipios
  (municipio_rfb_codigo, uf_sigla, municipio_id)`; `int_rfb__estabelecimentos` (competência mais
  recente, + `situacao`, `motivo`, `cnae_principal_descricao`, `municipio_id`,
  `competencia_receita`); `int_rfb__socios` (+ `tipo_socio` em `pessoa_juridica`,
  `pessoa_fisica`, `estrangeiro`; `nome_socio_normalizado`; `qualificacao`);
  `int_rfb__empresas` (uma linha por `cnpj_raiz`, com `data_abertura` = menor início de
  atividade entre os estabelecimentos, situação e município da matriz, Simples/MEI, contagens).

- [ ] **Passo 1:** `git checkout proto/onda-c1 -- dbt/models/intermediate/int_rfb__raizes_interesse.sql dbt/models/intermediate/int_rfb__municipios.sql dbt/models/intermediate/int_rfb__estabelecimentos.sql dbt/models/intermediate/int_rfb__socios.sql dbt/models/intermediate/int_rfb__empresas.sql dbt/models/intermediate/rfb.yml`.
- [ ] **Passo 2:** rode a **Verificação dbt (lago vazio)**. Esperado: sem `ERROR` nem `FAIL`, com
  `PASS int_rfb__empresas::abertura_e_o_estabelecimento_mais_antigo`, e o arquivo
  `dbt/tests/lago_vazio/rfb_raizes_interesse.parquet` criado (ignorado pelo git).
- [ ] **Passo 3 (mutação):** em `int_rfb__empresas.sql`, troque
  `min(data_inicio_atividade) as data_abertura` por `max(data_inicio_atividade) as data_abertura`.
  O teste unitário **deve falhar**. Restaure e rode de novo: verde.
- [ ] **Passo 4:** ruff e pytest completos verdes; `git status` sem nenhum `.parquet`. Commit:
  `feat(dbt): intermediários da Receita e raízes de CNPJ de interesse`.

### Tarefa 7: Dimensões públicas e o teste `sem_dados_pessoais`

**Files:**
- Create: `dbt/models/marts/dim_empresa.sql`, `dbt/models/marts/dim_estabelecimento.sql`,
  `dbt/models/marts/receita.yml`, `dbt/tests/generic/sem_dados_pessoais.sql`

**Interfaces:**
- Consumes: Tarefa 6.
- Produces: marts `dim_empresa` (chave `cnpj_raiz`) e `dim_estabelecimento` (chave `cnpj`), sem
  endereço, contato nem sócios; teste genérico `sem_dados_pessoais` (falha com cada coluna de
  endereço, contato, sócio ou CPF no modelo).

- [ ] **Passo 1:** `git checkout proto/onda-c1 -- dbt/models/marts/dim_empresa.sql dbt/models/marts/dim_estabelecimento.sql dbt/models/marts/receita.yml dbt/tests/generic/sem_dados_pessoais.sql`.
- [ ] **Passo 2:** rode a **Verificação dbt (lago vazio)**. Esperado: sem `ERROR` nem `FAIL`.
- [ ] **Passo 3 (mutação):** em `dim_estabelecimento.sql`, troque a linha `    uf_sigla,` por
  `    uf_sigla, cnpj as cep,` e rode a verificação: `sem_dados_pessoais_dim_estabelecimento_`
  **deve dar FAIL 1**. Restaure e rode de novo: verde.
- [ ] **Passo 4:** ruff e pytest completos verdes. Commit:
  `feat(dbt): dim_empresa e dim_estabelecimento, sem endereço, contato nem sócios`.

### Tarefa 8: Alertas de empresa irregular e de empresa recém-aberta

**Files:**
- Create: `dbt/macros/rfb.sql` (`rfb_fatos()`: cota, pagamento de emenda e contrato com CNPJ, sem
  os registros com problema de qualidade), `dbt/models/marts/alerta_pagamento_empresa_irregular.sql`,
  `dbt/models/marts/alerta_empresa_recem_aberta.sql`, `dbt/models/marts/alertas_receita_fatos.yml`

**Interfaces:**
- Consumes: Tarefas 6 e 7; marts `fct_despesa_cota_parlamentar`, `fct_emenda_pagamento`,
  `fct_contrato_federal`, `dim_autor_emenda`.
- Produces: macro `rfb_fatos()` com `origem, fato_id, data_fato, valor, cnpj, cnpj_raiz,
  parlamentar_id`; os dois alertas (colunas na spec, seção 5, e em `docs/modelos-de-dados.md`).

- [ ] **Passo 1:** `git checkout proto/onda-c1 -- dbt/macros/rfb.sql dbt/models/marts/alerta_pagamento_empresa_irregular.sql dbt/models/marts/alerta_empresa_recem_aberta.sql dbt/models/marts/alertas_receita_fatos.yml`.
- [ ] **Passo 2:** rode a **Verificação dbt (lago vazio)**. Esperado: sem `ERROR` nem `FAIL`, com
  `PASS ...::empresa_irregular_na_data_do_fato` e `PASS ...::empresa_recem_aberta_ate_180_dias`.
- [ ] **Passo 3 (mutação 1):** em `alerta_empresa_recem_aberta.sql`, troque `<= 180` por `<= 181`:
  `empresa_recem_aberta_ate_180_dias` **deve falhar**. Restaure.
- [ ] **Passo 4 (mutação 2):** em `alerta_pagamento_empresa_irregular.sql`, apague a linha
  `and coalesce(s.motivo_codigo, '') not in ('02', '03', '04')`:
  `empresa_irregular_na_data_do_fato` **deve falhar** (a incorporação entraria). Restaure e rode
  de novo: verde.
- [ ] **Passo 5:** ruff e pytest completos verdes. Commit:
  `feat(dbt): alertas de pagamento a empresa irregular e de empresa recém-aberta`.

### Tarefa 9: Alertas de sócios em comum na licitação e de parlamentar sócio de fornecedor

**Files:**
- Create: `dbt/models/marts/alerta_licitacao_socios_em_comum.sql`,
  `dbt/models/marts/alerta_parlamentar_socio_fornecedor.sql`,
  `dbt/models/marts/alertas_receita_socios.yml`

**Interfaces:**
- Consumes: Tarefas 5, 6 e 8 (`rfb_fatos()`); `int_cgu__licitacao_participantes`,
  `stg_senado__senadores`, `dim_parlamentar`.
- Produces: os dois alertas (colunas na spec, seção 5, e em `docs/modelos-de-dados.md`).

- [ ] **Passo 1:** `git checkout proto/onda-c1 -- dbt/models/marts/alerta_licitacao_socios_em_comum.sql dbt/models/marts/alerta_parlamentar_socio_fornecedor.sql dbt/models/marts/alertas_receita_socios.yml`.
- [ ] **Passo 2:** rode a **Verificação dbt (lago vazio)**. Esperado: **`PASS=203`**, sem `ERROR`
  nem `FAIL`, com `PASS ...::socios_em_comum_antes_da_licitacao` e
  `PASS ...::parlamentar_socio_por_nome_e_cpf`.
- [ ] **Passo 3 (mutação 1):** em `alerta_licitacao_socios_em_comum.sql`, apague a linha
  `        and sb.data_entrada <= a.data_licitacao`: `socios_em_comum_antes_da_licitacao`
  **deve falhar** (o sócio que entrou depois contaria). Restaure.
- [ ] **Passo 4 (mutação 2):** em `alerta_parlamentar_socio_fornecedor.sql`, troque
  `and (p.cpf_meio is null or substr(s.documento_socio, 4, 6) = p.cpf_meio)` por nada (apague o
  trecho): `parlamentar_socio_por_nome_e_cpf` **deve falhar** (o homônimo entraria). Restaure e
  rode de novo: verde.
- [ ] **Passo 5:** ruff e pytest completos verdes. Commit:
  `feat(dbt): alertas de sócios em comum na licitação e de parlamentar sócio de fornecedor`.

### Tarefa 10: Agente investigador e documentação

**Files:**
- Modify: `agente/preparar.py` (cria Parquet vazio para fonte sem coleta antes do dbt),
  `tests/agente/test_preparar.py`, `agente/avaliacao.py` (caso plantado: BETA ENGENHARIA baixada
  recebendo emenda, que deve ser confirmado), `tests/agente/test_cli_avaliacao.py`,
  `.claude/agents/investigador.md` (cadastro da Receita, sócios no privado, lentes novas),
  `docs/modelos-de-dados.md` (fontes, dimensões, alertas, intermediários e o teste novo)

**Interfaces:**
- Consumes: `coletor.esquemas.ARQUIVO_ESQUEMAS`, `carregar_esquemas`, `garantir_fontes`.
- Produces: `agente.avaliacao.BETA`; chave nova `"caso de empresa baixada confirmado"` em
  `verificar(estado)`; tabelas `marts.dim_empresa` e `marts.alerta_pagamento_empresa_irregular`
  no lago de avaliação.

- [ ] **Passo 1:** `git checkout proto/onda-c1 -- agente/preparar.py tests/agente/test_preparar.py agente/avaliacao.py tests/agente/test_cli_avaliacao.py .claude/agents/investigador.md docs/modelos-de-dados.md`.
- [ ] **Passo 2:** `uv run pytest -q tests/agente/test_preparar.py tests/agente/test_cli_avaliacao.py`.
  Esperado: **17 passed**.
- [ ] **Passo 3 (mutação):** em `agente/preparar.py`, troque
  `garantir_fontes(config.lago, carregar_esquemas(config.raiz / "dbt"))` por `pass`.
  `test_preparar_cria_parquet_vazio_para_fonte_ainda_sem_coleta` **deve falhar**. Restaure e
  confirme.
- [ ] **Passo 4:** ruff e pytest completos verdes (**297 passed**). Commit:
  `feat(agente): cadastro da Receita no investigador, caso plantado de empresa baixada e docs`.

### Tarefa 11: Workflow mensal da Receita

**Files:**
- Create: `.github/workflows/receita.yml`

**Interfaces:**
- Consumes: Tarefas 1 a 6 (`coletor executar --grupo receita`, `int_rfb__raizes_interesse`).
- Produces: workflow `receita` (segunda 06:00 UTC e `workflow_dispatch`; 180 min; grupo de
  concorrência `pipeline`; restaura o lago cifrado, roda `dbt run --select
  +int_rfb__raizes_interesse`, `coletor executar --grupo receita`, salva o estado e o cache
  cifrado; não publica).

- [ ] **Passo 1:** `git checkout proto/onda-c1 -- .github/workflows/receita.yml`.
- [ ] **Passo 2:** confira que o YAML carrega e que as ações estão fixadas por SHA, iguais às do
  `pipeline.yml`:
  `uv run python -c "import yaml; d = yaml.safe_load(open('.github/workflows/receita.yml', encoding='utf-8')); print(d['concurrency'], d['jobs']['receita']['timeout-minutes'])"`.
  Esperado: `{'group': 'pipeline', 'cancel-in-progress': False} 180`.
- [ ] **Passo 3:** ruff e pytest completos verdes (**297 passed**) e a **Verificação dbt (lago
  vazio)** com `PASS=203`. Commit: `ci: workflow mensal da base do CNPJ da Receita`.
- [ ] **Passo 4:** `git push -u origin feat/onda-c1-receita` e abra o PR para `main` com o título
  `Onda C1: cadastro de empresas da Receita Federal`. O push de um arquivo em
  `.github/workflows/` exige credencial com escopo `workflow`. **Não faça merge**: o Claude revisa.

## Depois do merge (Claude, com o ok do usuário)

1. Disparar o `receita.yml` por `workflow_dispatch` e acompanhar: tempo do download e do recorte
   no runner (no protótipo local: ~50 min), linhas mantidas por grupo (esperado: ~250 mil
   empresas, ~657 mil estabelecimentos, ~388 mil sócios, ~159 mil no Simples) e 1.814 deputados
   no detalhe. Se passar de 90 minutos, dividir os grupos em semanas (spec, seção 8).
2. No pipeline diário seguinte: conferir os marts novos publicados no R2 e os números dos alertas
   contra a seção 10 da spec.
3. Rodar o `preparar` do agente e a avaliação com o caso plantado novo.
