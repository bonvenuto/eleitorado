# Ingestão de dados públicos no BigQuery: fundação e onda A

- **Data:** 2026-10-03
- **Status:** rascunho para revisão
- **Base:** [mapeamento-dados-publicos.md](../../mapeamento-dados-publicos.md) e [mapeamento-dados-publicos.json](../../mapeamento-dados-publicos.json)

## 1. Objetivo

Montar um repositório com os dados completos dos portais de transparência mapeados no levantamento, para monitorar o governo e as ações públicas, procurar inconsistências e gerar insights. A primeira entrega é a camada de dados no BigQuery, transformada com dbt. Uma web app virá depois e vai consumir os marts desta camada.

Ingerir as 21 instituições do levantamento num único ciclo seria grande demais. O trabalho foi dividido em sub-projetos, cada um com spec e plano próprios:

1. **Fundação e onda A (esta spec):** coletor, camada raw, controle de coletas, projeto dbt, orquestração, infraestrutura e monitoramento, validados com fontes do Legislativo, sanções da CGU e IBGE Localidades.
2. **Ondas seguintes** (seção 13), aproveitando a fundação.

## 2. Escopo

### Dentro

- Coletor Python que implementa o contrato de coleta do levantamento: origem, competência, hash, data de coleta e original preservado.
- Camada raw no Cloud Storage (GCS) e no BigQuery, com tabelas de controle no dataset `meta`.
- Projeto dbt com staging, intermediate e marts da onda A, incluindo dois alertas.
- Execução diária agendada, deploy automatizado, infraestrutura como código, travas de custo e aviso de falha.
- Fontes da onda A (detalhes na seção 6.8): deputados e CEAP (Câmara), senadores e CEAPS (Senado), CEIS e CNEP (CGU) e municípios (IBGE).

### Fora

- Web app e a camada que vai servi-la (cache, API, banco de leitura).
- Demais fontes do levantamento.
- Interfaces restritas ou pagas (Conecta, Serpro, OAuth da ANS).
- TSE, que não consta do levantamento.
- API da CGU com token. A onda A usa só os downloads públicos.
- Harmonização das categorias de despesa entre Câmara e Senado.

## 3. Premissas e restrições

- **Esfera federal.** Estados e municípios entram apenas por meio de fontes federais que os incluem.
- **"Completo" significa todo o histórico que a fonte oferece.** CEIS e CNEP são exceção: a CGU mantém disponível só o arquivo diário mais recente (em 2026-10-03, as datas anteriores a 2026-10-02 retornavam HTTP 403). O histórico de sanções começa na primeira coleta.
- **Custo recorrente perto de zero.** O projeto GCP fica na conta de faturamento conectada ao gcloud, que tem crédito mensal do programa de desenvolvedor do Google, suficiente para o custo estimado (seção 10). A conta do trial de US$ 300 não é usada.
- **Dados no Brasil.** Todos os recursos ficam em `southamerica-east1`.
- **LGPD.** CPF completo nunca chega ao dataset `marts` (seção 7.6). Nomes seguem como publicados pela fonte.
- **Ferramentas.** Python 3.12 com uv, dbt Core com dbt-bigquery, Terraform, Docker, GitHub e GitHub Actions. Desenvolvimento em Windows 11.

## 4. Critérios de sucesso

1. O job roda todo dia às 07:30 (horário de Brasília) sem intervenção, por 7 dias seguidos.
2. Toda coleta fica registrada em `meta.coletas` com URL, parâmetros, hashes, bytes, linhas, competência, horários e status.
3. Repetir uma coleta no mesmo dia produz o mesmo raw. `coletor recarregar` refaz uma partição a partir do original no GCS, sem acessar a fonte.
4. O histórico está carregado: CEAP e CEAPS de 2008 até o ano corrente, deputados e senadores da legislatura 53 em diante e municípios. CEIS e CNEP desde a primeira coleta.
5. `dbt build` passa, incluindo a reconciliação dos totais da cota parlamentar com o raw.
6. Os dois alertas são recalculados a cada execução.
7. Um teste automatizado garante que nenhuma coluna de `marts` contém CPF completo.
8. O custo fica dentro da camada gratuita e do crédito. Orçamento, cota diária do BigQuery e `maximum_bytes_billed` estão ativos.
9. O aviso de falha chega por e-mail quando nenhuma execução agendada do dia termina com sucesso. Isso é verificado com uma falha simulada.

## 5. Arquitetura

```
Cloud Scheduler (diário, 07:30 America/Sao_Paulo)
  └─> Cloud Run Job "pipeline"  (imagem única: coletor + projeto dbt)
        1. coletor executar   coleta as fontes cujo prazo venceu
             ├─> GCS          originais imutáveis + Parquet de carga
             ├─> BigQuery     raw_<órgão>
             └─> BigQuery     meta.coletas
        2. dbt build          staging → intermediate → marts, com testes
        3. resumo da execução em meta.execucoes

GitHub Actions: CI, deploy da imagem e vigia diário
Terraform: infraestrutura do projeto
```

### 5.1 Região e projeto

- Projeto GCP novo e dedicado, vinculado à conta de faturamento com o crédito de desenvolvedor. O id do projeto é uma variável do Terraform.
- Tudo fica em `southamerica-east1`: bucket, datasets do BigQuery, Cloud Run, Cloud Scheduler e Artifact Registry.
- Consequência: não dá para cruzar em SQL com datasets públicos hospedados na localização `US`, como os da Base dos Dados. Conferências de contagem com eles são feitas em consultas separadas.

### 5.2 Datasets do BigQuery

| Dataset | Conteúdo | Quem grava | Quem lê |
|---|---|---|---|
| `meta` | coletas, execuções e manifesto publicado | pipeline | pipeline, você, vigia |
| `raw_camara`, `raw_senado`, `raw_cgu`, `raw_ibge` | dado bruto e colunas de controle | pipeline | pipeline, você |
| `replay` | originais recarregados para reconstruir históricos (seção 7.4) | pipeline | pipeline, você |
| `staging` | views tipadas | pipeline (dbt) | pipeline, você |
| `intermediate` | unificações e históricos | pipeline (dbt) | pipeline, você |
| `marts` | contrato com a web app | pipeline (dbt) | pipeline, você, futura web app |
| `ci` | relações temporárias dos testes unitários do dbt | CI | CI |

CPF completo existe em raw, staging e intermediate. Por isso a web app recebe acesso apenas a `marts`.

### 5.3 Ambientes

- **Produção:** os datasets da tabela acima e os prefixos `originais/` e `carga/` do bucket.
- **Desenvolvimento do coletor:** datasets com sufixo `_dev` (`meta_dev`, `raw_camara_dev` etc.) e prefixo `dev/` no bucket.
- **Desenvolvimento do dbt:** o target `dev` grava em `dev_<usuário>_staging`, `dev_<usuário>_intermediate` e `dev_<usuário>_marts`, lendo o raw de produção.

### 5.4 Repositório

```
pyproject.toml, uv.lock   ambiente Python único: coletor + dbt-bigquery
coletor/                  pacote do coletor (CLI `coletor`)
tests/                    testes do coletor (pytest) e fixtures
fontes/                   manifesto: camara.yaml, senado.yaml, cgu.yaml, ibge.yaml
dbt/                      projeto dbt (models/, macros/, tests/, profiles.yml)
infra/                    Terraform
.github/workflows/        ci.yml, deploy.yml, vigia.yml
Dockerfile                python:3.12-slim + uv; copia coletor, fontes e dbt; roda `dbt deps` no build
.gitattributes            força LF em scripts, Dockerfile e YAML
docs/
```

## 6. Coletor

### 6.1 Manifesto

Cada órgão tem um arquivo em `fontes/`. O coletor valida o manifesto na inicialização e, a cada execução, publica o conteúdo em `meta.fontes`. Exemplo:

```yaml
# fontes/camara.yaml
orgao: camara
nome: Câmara dos Deputados
portal: https://dadosabertos.camara.leg.br/
recursos:
  - id: ceap
    descricao: Despesas da Cota para o Exercício da Atividade Parlamentar
    fonte_oficial: https://dadosabertos.camara.leg.br/
    adaptador: arquivo
    url: https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip
    publicacao: por_competencia
    competencia: {tipo: ano, inicio: 2008}
    cadencia: {corrente: diaria, anteriores: semanal}
    formato:
      compressao: zip
      arquivo: Ano-{ano}.csv
      tipo: csv
      encoding: utf-8-sig
      delimitador: ";"
```

Campos de cada recurso:

| Campo | Uso |
|---|---|
| `id`, `descricao`, `fonte_oficial` | identificação; o id completo é `<órgão>.<recurso>` |
| `condicoes_uso` | texto ou link das condições de reutilização publicadas pelo portal, preenchido na implementação |
| `adaptador` | `arquivo` ou `api_json` |
| `url` | endereço com marcadores (`{ano}`, `{data}`, `{legislatura}`) |
| `publicacao` | `snapshot` ou `por_competencia` (seção 6.3) |
| `competencia` | tipo (`ano`, `data_arquivo`, `data_coleta`), início e forma de descoberta |
| `cadencia` | `diaria`, `semanal` ou `mensal`; em `por_competencia`, uma para a competência corrente e outra para as anteriores |
| `formato` | compressão, arquivo dentro do ZIP, tipo, encoding, delimitador, linhas a pular |
| `paginacao`, `iteracao`, `registros` | só em `api_json` (seção 6.2) |
| `acesso` | `publico` ou `token`, com o nome do segredo |

### 6.2 Adaptadores

- **`arquivo`:** GET seguindo redirecionamentos, download em streaming para arquivo temporário e descompactação quando `formato.compressao: zip`.
- **`api_json`:** GET em JSON.
  - `paginacao`: `links_next` (segue `links[rel=next]` até acabar) ou `nenhuma`.
  - `iteracao`: repete a chamada para cada valor de um parâmetro, por exemplo `idLegislatura` de 53 até a legislatura atual.
  - `registros`: caminho da lista de registros dentro do JSON, como `dados` ou `ListaParlamentarLegislatura.Parlamentares.Parlamentar`, ou a própria raiz.
- Adaptadores para OData, CKAN, WFS e FTP entram nas ondas que precisarem deles.

### 6.3 Tipos de publicação e partições

| Tipo | Significado | Partição no raw | Retenção no raw | Recoleta |
|---|---|---|---|---|
| `snapshot` | estado completo numa data | por dia de `_competencia_data` (data de referência) | 60 dias, por expiração de partição | conforme a cadência |
| `por_competencia` | dados de um período (ano ou mês) | por ano ou mês de `_competencia_data` | versão mais recente de cada competência, sem expiração | competência corrente na cadência própria; anteriores toda semana |

- A data de referência de um snapshot é a data do arquivo, quando a fonte informa (CGU). Nos demais casos, é a data da coleta no fuso de Brasília.
- Toda carga substitui só a partição alvo: load job com `WRITE_TRUNCATE` e decorador de partição. Por isso repetir a coleta é idempotente.
- Para reconstruir históricos além de 60 dias, `coletor recarregar --destino replay` carrega os originais arquivados no dataset `replay`, que não tem expiração (seção 7.4).

### 6.4 Fluxo de uma coleta (recurso e competência)

1. Gera um `coleta_id` (UUID).
2. Baixa os dados em streaming:
   - até 5 tentativas, com espera exponencial e jitter, respeitando `Retry-After`;
   - timeout de 10 s para conexão e de 120 s para leitura.
3. Calcula dois SHA-256:
   - **`sha256_arquivo`:** sobre os bytes como baixados. Em APIs, sobre os corpos das páginas concatenados na ordem em que foram recebidos.
   - **`sha256_conteudo`:** é a base da deduplicação.
     - Em arquivos, é calculado sobre os bytes descompactados, porque o ZIP pode mudar por metadados internos sem que o conteúdo mude.
     - Em APIs, é calculado sobre os registros extraídos em JSON canônico (chaves ordenadas). Assim, carimbos voláteis da resposta, como `Metadados.Versao` do Senado, não alteram o hash.
4. Se o `sha256_conteudo` for igual ao da última coleta bem-sucedida da mesma competência, registra `sem_alteracao` e encerra.
5. Grava o original em `originais/<órgão>/<recurso>/competencia=<c>/<AAAAMMDDTHHMMSS>_<sha256_conteudo[:12]>.<ext>`.
   - Em APIs, o original é um `.jsonl.gz` com uma linha por página, contendo URL, status HTTP e corpo como recebido.
   - O nome inclui data, hora e hash, então nenhum objeto é sobrescrito.
6. Converte para Parquet com pyarrow, em lotes, gravando em `carga/<órgão>/<recurso>/competencia=<c>/<coleta_id>.parquet`.
   - **CSV:** todas as colunas como STRING. Os nomes são normalizados: sem acento e em minúsculas. Cada sequência de caracteres não alfanuméricos vira um único `_`, sem `_` no início ou no fim. Exemplos:
     - `ABRAGÊNCIA DA SANÇÃO` vira `abragencia_da_sancao`, mantendo o erro de grafia da fonte;
     - `RAZÃO SOCIAL - CADASTRO RECEITA` vira `razao_social_cadastro_receita`.

     O mapeamento do nome original para o normalizado fica em `meta.coletas`.
   - **API:** uma linha por registro, com o registro inteiro na coluna `payload` (JSON).
   - **Colunas de controle:**
     - `_coleta_id`
     - `_competencia`: texto, como `2025` ou `2026-10-02`
     - `_competencia_data`: DATE
     - `_linha`: posição no arquivo ou na resposta
     - `_arquivo_original`: URI no GCS
     - `_carregado_em`: TIMESTAMP em UTC
7. Carrega no BigQuery por load job, que é gratuito, com `WRITE_TRUNCATE` na partição e as opções `ALLOW_FIELD_ADDITION` e `ALLOW_FIELD_RELAXATION`. A tabela é criada na primeira carga, com partição e expiração definidas pelo tipo de publicação.
8. Grava a linha da coleta em `meta.coletas` por load job, com status `carregada`.

Se algum passo falhar, a coleta é registrada com status `falha` e a mensagem de erro, e os demais recursos seguem. O load é o último passo e é atômico, portanto uma falha nunca deixa carga parcial no raw.

### 6.5 Tabelas de controle

**`meta.coletas`:** uma linha por coleta, particionada por dia de `iniciada_em`.

| Coluna | Tipo | Descrição |
|---|---|---|
| `coleta_id` | STRING | UUID |
| `execucao_id` | STRING | execução que disparou a coleta |
| `orgao`, `recurso`, `competencia` | STRING | identificação |
| `url` | STRING | URL final após redirecionamentos, sem segredos |
| `parametros` | JSON | parâmetros não secretos |
| `iniciada_em`, `finalizada_em` | TIMESTAMP | em UTC |
| `status` | STRING | `carregada`, `sem_alteracao` ou `falha` |
| `http_status` | INT64 | último status HTTP |
| `http_last_modified`, `http_etag` | STRING | cabeçalhos informados pela fonte |
| `bytes_arquivo`, `linhas` | INT64 | volume |
| `sha256_arquivo`, `sha256_conteudo` | STRING | hashes (seção 6.4) |
| `arquivo_original`, `arquivo_carga` | STRING | URIs `gs://` |
| `colunas` | JSON | nome original → nome normalizado |
| `esquema_alterado` | BOOL | cabeçalho diferente da última coleta bem-sucedida |
| `erro` | STRING | mensagem de falha |
| `versao_coletor` | STRING | git SHA da imagem |

**`meta.execucoes`:** uma linha por execução do pipeline. Colunas: `execucao_id`, `origem` (`agendada` ou `manual`), `iniciada_em`, `finalizada_em`, `status` (`sucesso` ou `falha`), `coletas_carregadas`, `coletas_sem_alteracao`, `coletas_falha`, `dbt_status`, `dbt_testes_com_erro` e `versao`.

**`meta.fontes`:** o manifesto publicado, com uma linha por recurso, substituído a cada execução.

### 6.6 Comandos

- `coletor executar [--recursos camara.ceap,...]`: coleta o que está no prazo, considerando a cadência e a última coleta bem-sucedida.
- `coletor coletar <recurso> [--competencia C | --de C1 --ate C2] [--forcar]`: coleta manual e backfill. `--forcar` ignora a deduplicação.
- `coletor recarregar <recurso> --competencia C [--coleta-id ID] [--destino raw|replay]`: refaz a carga a partir do original no GCS.
- `coletor fontes`: lista o manifesto e o estado de cada recurso.
- `coletor pipeline`: entrypoint da imagem. Roda `coletor executar`, depois `dbt build --target prod`, e grava `meta.execucoes`. Executa todas as etapas mesmo quando uma falha e só no fim sai com código diferente de zero.

A configuração vem de variáveis de ambiente: `ELEITORADO_PROJETO`, `ELEITORADO_BUCKET`, `ELEITORADO_REGIAO` (`southamerica-east1`) e `ELEITORADO_AMBIENTE` (`dev` ou `prod`).

### 6.7 Mudança de esquema

- Cabeçalho (em CSV) ou conjunto de chaves de primeiro nível (em API) diferente da última coleta bem-sucedida marca `esquema_alterado = true`.
- Colunas novas entram no raw automaticamente. Colunas que deixam de vir ficam nulas nas cargas novas.
- O mart `monitor_fontes` destaca as mudanças de esquema dos últimos 30 dias. Se sumir uma coluna que o staging usa, os testes do dbt falham.

### 6.8 Fontes da onda A

| Recurso | Adaptador | Endereço | Publicação e competência | Cadência |
|---|---|---|---|---|
| `camara.deputados` | `api_json`, paginação `links_next`, `itens=100`, iteração `idLegislatura` de 53 até a atual | `https://dadosabertos.camara.leg.br/api/v2/deputados` | snapshot, data da coleta | semanal |
| `camara.ceap` | `arquivo`, ZIP com CSV em UTF-8 com BOM, separador `;` | `https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip` | por competência, ano, de 2008 até o atual | ano corrente diária, anteriores semanal |
| `senado.senadores` | `api_json`, sem paginação | `https://legis.senado.leg.br/dadosabertos/senador/lista/legislatura/53/{legislatura}.json` | snapshot, data da coleta | semanal |
| `senado.ceaps` | `api_json`, sem paginação | `https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/despesas_ceaps/{ano}` | por competência, ano, de 2008 até o atual | ano corrente diária, anteriores semanal |
| `cgu.ceis` | `arquivo`, ZIP com CSV em Windows-1252, separador `;` | `https://portaldatransparencia.gov.br/download-de-dados/ceis/{data}` | snapshot, data do arquivo | diária |
| `cgu.cnep` | igual ao CEIS | `https://portaldatransparencia.gov.br/download-de-dados/cnep/{data}` | snapshot, data do arquivo | diária |
| `ibge.municipios` | `api_json`, sem paginação | `https://servicodados.ibge.gov.br/api/v1/localidades/municipios` | snapshot, data da coleta | mensal |

Observações verificadas em 2026-10-03:

- **Legislatura atual:** é calculada a partir da data. A 57ª vai de fevereiro de 2023 a janeiro de 2027, e a numeração muda em 1º de fevereiro a cada 4 anos. Câmara e Senado usam a mesma numeração.
- **`camara.deputados`:**
  - cerca de 9 páginas de 100 por legislatura;
  - o `id` da API é o mesmo `ideCadastro` da CEAP.
- **`camara.ceap`:**
  - 209.080 linhas em 2025, com decimal com ponto e datas ISO;
  - não há chave natural, porque o mesmo `ideDocumento` se repete em várias linhas (seção 7.5);
  - traz o CPF do deputado;
  - linhas de lideranças vêm sem `ideCadastro`.
- **`senado.senadores`:**
  - 681 parlamentares nas legislaturas 53 a 57;
  - `CodigoParlamentar` é o mesmo `codSenador` da CEAPS.
- **`senado.ceaps`:**
  - entra pela API administrativa, e não pelo CSV, porque a API traz `codSenador` e um `id` único por despesa, enquanto o CSV tem só o nome do senador;
  - cerca de 24 mil registros e 10 MB em 2025;
  - registros antigos vêm sem fornecedor e sem data.
- **`cgu.ceis` e `cgu.cnep`:**
  - só o arquivo mais recente fica disponível;
  - a data é descoberta no trecho `arquivos.push({"ano": ..., "mes": ..., "dia": ...})` da página `https://portaldatransparencia.gov.br/download-de-dados/<ceis|cnep>`. Se a descoberta falhar, o coletor tenta diretamente as datas de D-1 a D-3;
  - o arquivo do dia é publicado no fim da tarde;
  - `CÓDIGO DA SANÇÃO` é único em cada arquivo;
  - decimal com vírgula e datas no formato `dd/mm/aaaa`;
  - o CNEP tem a coluna extra `VALOR DA MULTA`;
  - o CPF de pessoa física sancionada vem completo.
- **`ibge.municipios`:** um JSON de 2,4 MB.

## 7. Modelagem dbt

### 7.1 Projeto

- dbt Core com dbt-bigquery, na versão estável mais recente no início da implementação, mais o pacote `dbt_utils`.
- `profiles.yml` versionado em `dbt/`, sem segredos:
  - método `oauth` (ADC no computador local e conta de serviço no Cloud Run);
  - `project` vindo de `ELEITORADO_PROJETO`;
  - `location: southamerica-east1`;
  - `maximum_bytes_billed` de 10 GiB;
  - targets `dev`, `prod` e `ci`.
- A macro `generate_schema_name` usa os schemas configurados (`staging`, `intermediate`, `marts`) em `prod` e `dev_<usuário>_<schema>` em `dev`.

### 7.2 Camadas

| Camada | Materialização | Papel |
|---|---|---|
| sources | — | `raw_*` e `meta` |
| staging | view | tipos, nomes, extração do JSON e normalização de documentos. Nos snapshots, expõe a data de referência mais recente |
| intermediate | table ou incremental | unificação entre fontes e históricos SCD2 |
| marts | table, particionada e clusterizada quando grande | contrato com a web app |

### 7.3 Convenções

- **Nomes:** modelos e colunas em português, em snake_case. Prefixos: `stg_<órgão>__<recurso>`, `int_<domínio>__<descrição>`, `dim_`, `fct_`, `alerta_` e `monitor_`.
- **Identificadores:** sempre STRING, preservando zeros à esquerda.
- **Macros de documento.** Desde 31/07/2026 a Receita emite CNPJ alfanumérico: as 12 primeiras posições aceitam dígitos e letras maiúsculas, e as 2 últimas continuam numéricas ([perguntas e respostas da Receita](https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/publicacoes/perguntas-e-respostas/cnpj/cnpj-alfanumerico.pdf)). Por isso as macros não podem tratar CNPJ como só números.
  - `normalizar_documento`: converte para maiúsculas e mantém só dígitos e letras, removendo pontuação e espaços;
  - `tipo_documento`: CPF se tiver 11 dígitos; CNPJ se tiver 14 caracteres, sendo 12 dígitos ou letras seguidos de 2 dígitos; caso contrário, `invalido`;
  - `documento_valido`: confere os dígitos verificadores. No CPF, pela regra tradicional. No CNPJ, numérico ou alfanumérico, por módulo 11, com cada caractere valendo seu código ASCII menos 48;
  - `cnpj_raiz`: os 8 primeiros caracteres;
  - `mascarar_cpf`: devolve no formato `***.456.789-**`.
- **Tipos:** valores em NUMERIC, datas em DATE, instantes em TIMESTAMP UTC. A conversão segue cada fonte:
  - Câmara: ponto decimal e datas ISO;
  - CGU: vírgula decimal e `dd/mm/aaaa`;
  - Senado: números e datas ISO no JSON.
- **Rastreabilidade:** toda linha de mart traz o `_coleta_id` de origem.

### 7.4 Históricos (SCD2)

- Os históricos ficam nos modelos `int_cgu__sancoes_historico` e `int_parlamentares__historico`. Ambos são incrementais e têm as colunas:
  - `valido_de` e `valido_ate`, definidas pela data de referência da publicação;
  - `evento`: `inclusao`, `alteracao` ou `exclusao`.
- A cada execução, o modelo processa em ordem as datas de referência do raw que ainda não foram incorporadas e compara cada registro com o estado vigente no histórico, usando um hash dos atributos.
- Um registro que deixa de aparecer num snapshot ganha um evento `exclusao`, e o `valido_ate` da versão vigente é fechado. Se ele voltar a aparecer, recebe uma nova `inclusao`.
- O `dbt snapshot` não é usado porque, com a estratégia `check`, ele registra cada mudança com o horário da execução. Um dia sem rodar ou um reprocessamento deixaria as datas erradas.
- Para uma reconstrução completa, roda-se `--full-refresh` com a variável `fonte_historico: replay`. Assim o modelo lê o dataset `replay`, carregado antes com `coletor recarregar --destino replay` a partir dos originais arquivados.

### 7.5 Marts da onda A

**`dim_uf`:** uma linha por UF, com `uf_id`, `uf_sigla`, `uf_nome`, `regiao_sigla` e `regiao_nome`.

**`dim_municipio`:** uma linha por município, com `municipio_id` (código IBGE de 7 dígitos), `municipio_nome`, `uf_sigla`, microrregião, mesorregião, região imediata e região intermediária.

**`dim_parlamentar`:** uma linha por parlamentar, com `parlamentar_id` (`camara:<id>` ou `senado:<CodigoParlamentar>`), `casa`, `id_origem`, `nome`, a `uf_sigla` e o `partido_sigla` mais recentes, `legislaturas` (array) e `url_foto` (só Câmara).

**`fct_despesa_cota_parlamentar`:** uma linha por linha de despesa publicada.
- **Grão:** a CEAP não tem chave natural. O mesmo `ideDocumento` se repete em várias linhas, como contas de telefone e trechos de passagem. Em 2025, 30.317 das 209.080 linhas compartilham documento com outra linha. Por isso o grão é a linha publicada, e não o documento.
- **Chave `despesa_id`:** no Senado, `senado:<id>`. Na Câmara, um hash do conteúdo da linha combinado com o número de ocorrência entre linhas idênticas.
- **Colunas:**
  - Beneficiário: `casa`, `parlamentar_id` (nulo para lideranças), `tipo_beneficiario` (`parlamentar` ou `lideranca`), `nome_beneficiario`, `uf_sigla` (na Câmara, vem da linha; no Senado, do mandato no cadastro) e `partido_sigla` (só Câmara).
  - Período: `ano`, `mes`, `data_competencia` (primeiro dia do mês) e `data_emissao`.
  - Despesa: `categoria` e `subcategoria`.
  - Fornecedor: `fornecedor_nome`, `fornecedor_documento` (CNPJ completo ou CPF mascarado), `fornecedor_tipo_documento`, `fornecedor_documento_valido` e `fornecedor_cnpj_raiz`.
  - Valores: `valor_documento`, `valor_glosa` (só Câmara) e `valor_reembolsado` (`vlrLiquido` na Câmara, `valorReembolsado` no Senado).
  - Documento: `numero_documento`, `url_documento` e `id_documento_origem`.
  - Colunas próprias de cada casa, com prefixo: `camara_passageiro`, `camara_trecho` e `senado_detalhamento`.
  - `_coleta_id`.
- **Armazenamento:** partição mensal por `data_competencia` e cluster por `casa`, `fornecedor_cnpj_raiz` e `parlamentar_id`.

**`fct_sancao`:** uma linha por sanção presente no arquivo mais recente.
- **Identificação:** `sancao_id` (`ceis:<código>` ou `cnep:<código>`) e `cadastro`.
- **Sancionado:** `tipo_pessoa`, `sancionado_documento` (CNPJ completo ou CPF mascarado), `sancionado_cnpj_raiz`, `sancionado_nome` e `razao_social_receita`.
- **Sanção:** `categoria`, `valor_multa` (só CNEP), `abrangencia`, `fundamentacao_legal` e `numero_processo`.
- **Datas:** `data_inicio`, `data_fim`, `data_publicacao` e `data_transito_julgado`.
- **Órgão sancionador:** `orgao_sancionador`, `uf_orgao_sancionador` e `esfera_orgao_sancionador`.
- `_coleta_id`.

**`fct_sancao_historico`:** expõe o SCD2 com as mesmas colunas de `fct_sancao`, mais `valido_de`, `valido_ate` e `evento`.

**`alerta_cota_fornecedor_sancionado`:** despesa cujo fornecedor tinha sanção na data da despesa.
- **Regra:** a `data_emissao` cai entre `data_inicio` e `coalesce(data_fim, '9999-12-31')` de alguma sanção do histórico (qualquer versão já vista) com documento correspondente.
- **Correspondência:**
  - pessoa física: CPF completo;
  - pessoa jurídica: CNPJ completo ou CNPJ raiz (8 dígitos), porque matriz e filiais são a mesma pessoa jurídica.

  O campo `tipo_correspondencia` (`cpf`, `cnpj` ou `cnpj_raiz`) informa qual delas foi usada.
- **Colunas:** `alerta_id`, `despesa_id`, `sancao_id`, `tipo_correspondencia`, dados resumidos da despesa e da sanção (incluindo `abrangencia` e `orgao_sancionador`), `regra` (texto fixo que descreve o critério) e o `_coleta_id` de cada lado.
- **Limites conhecidos:**
  - A CEAP reembolsa gastos do parlamentar e não é contratação pública. Além disso, a abrangência da sanção varia. Por isso o alerta é um indício para investigar, não a constatação de uma irregularidade.
  - Sanções retiradas do CEIS/CNEP antes da primeira coleta não aparecem. No arquivo de 2026-10-02, só 562 das 23.739 sanções do CEIS já tinham data final no passado, o que mostra que sanções vencidas costumam sair do cadastro.

**`alerta_cota_documento_invalido`:** despesa com documento de fornecedor preenchido e inválido, por tamanho ou por dígito verificador.
- **Colunas:** `alerta_id`, `despesa_id`, `documento_publicado` (mascarado quando tem 11 dígitos), `motivo` (`tamanho` ou `digito_verificador`), dados resumidos da despesa e `regra`.
- Documentos vazios ficam de fora, porque o Senado não informa fornecedor nos registros antigos.

**`monitor_fontes`:** uma linha por recurso, com:
- última coleta e última coleta bem-sucedida (`carregada` ou `sem_alteracao`);
- status;
- atraso em horas e limite da cadência;
- linhas da última carga;
- mudança de esquema nos últimos 30 dias.

### 7.6 LGPD

- O CPF completo aparece em três situações: deputados na CEAP, fornecedores pessoa física e sancionados pessoa física. Ele existe apenas em raw, staging e intermediate, que só a conta do pipeline e você acessam.
- Em `marts`, todo documento de pessoa física aparece mascarado (`***.456.789-**`). O CPF de deputado não vai para `marts`.
- CNPJ fica completo. Nomes seguem como publicados pela fonte.
- O teste genérico `sem_cpf_completo` é aplicado a todas as colunas de texto dos marts. Ele falha se algum valor for um CPF de 11 dígitos sem máscara, com ou sem pontuação.

### 7.7 Testes do dbt

- **Genéricos:**
  - `unique` e `not_null` nas chaves de todos os marts;
  - `relationships` de `fct_despesa_cota_parlamentar.parlamentar_id` para `dim_parlamentar` e das colunas de UF para `dim_uf`;
  - `accepted_values` em `casa`, `cadastro`, `tipo_pessoa`, `tipo_beneficiario` e `evento`.
- **Unitários (dbt unit tests):**
  - `documento_valido` (CPF, CNPJ numérico e CNPJ alfanumérico) e `mascarar_cpf`;
  - transições do SCD2: inclusão, alteração, exclusão e reinclusão;
  - sobreposição de datas e correspondência por CNPJ raiz no alerta de sanção;
  - chave da Câmara com linhas idênticas.
- **Reconciliação:** a soma de `valor_reembolsado` e a contagem de linhas por `casa` e `ano` em `fct_despesa_cota_parlamentar` têm de ser iguais às do raw.
- **LGPD:** o teste `sem_cpf_completo`.
- **Atraso das fontes:** um teste em `monitor_fontes` com severidade `warn` e `error` conforme a cadência:

  | Cadência | `warn` | `error` |
  |---|---|---|
  | diária | 30 h | 54 h |
  | semanal | 8 dias | 10 dias |
  | mensal | 35 dias | 40 dias |

  Esse teste substitui o `dbt source freshness`. O freshness acusaria atraso por engano quando a coleta termina como `sem_alteracao`, porque nesse caso o raw não recebe carga nova.

## 8. Operação

### 8.1 Execução

- **Cloud Scheduler `pipeline-diario`:** agenda `30 7 * * *` no fuso `America/Sao_Paulo`, chamando a API do Cloud Run Jobs com a conta `scheduler`. Nesse horário, os arquivos da Câmara e do Senado já foram regerados durante a madrugada, e o da CGU foi publicado no fim da tarde anterior (horários observados em 2026-10-03).
- **Cloud Run Job `pipeline`:** 1 tarefa, 1 vCPU, 2 GiB de memória, timeout de 3.600 s e 1 retentativa. Usa a conta de serviço `pipeline` e executa o comando `coletor pipeline`.
- **Falhas:** a falha de uma fonte não interrompe as outras nem o dbt. O job termina com erro se houve qualquer falha de coleta ou algum teste com severidade `error`.

### 8.2 Infraestrutura (Terraform em `infra/`)

- **Estado remoto:** bucket `<projeto>-tfstate`, criado no bootstrap.
- **APIs habilitadas:** Cloud Run, Cloud Scheduler, Artifact Registry, BigQuery, Cloud Storage, IAM, IAM Credentials, STS, Billing Budgets e Service Usage.
- **Bucket `<projeto>-dados`:** em `southamerica-east1`, com acesso uniforme e prevenção de acesso público. Ciclo de vida:
  - `originais/` e `dev/originais/` mudam para a classe Archive aos 30 dias e nunca são excluídos;
  - `carga/` e `dev/carga/` são excluídos aos 7 dias.
- **BigQuery:** os datasets da seção 5.2 e as versões `_dev`, em `southamerica-east1`. As tabelas são criadas pelo coletor e pelo dbt.
- **Artifact Registry `eleitorado`:** repositório Docker com política de limpeza que mantém as 2 versões mais recentes.
- **Contas de serviço:**

| Conta | Papéis |
|---|---|
| `pipeline` | BigQuery Job User no projeto; BigQuery Data Editor em `meta`, `raw_*`, `replay`, `staging`, `intermediate` e `marts`; Storage Object Creator e Storage Object Viewer no bucket (cria objetos, mas não apaga nem sobrescreve). Os datasets `_dev` são usados com as suas credenciais, não com as do pipeline |
| `scheduler` | Cloud Run Invoker no job |
| `deployer` | Artifact Registry Writer no repositório; Cloud Run Developer no job; Service Account User na conta `pipeline` |
| `ci` | BigQuery Job User no projeto; BigQuery Data Viewer em `meta` (usado pelo vigia); BigQuery Data Editor em `ci` |

- **Workload Identity Federation:** pool `github` com provider OIDC restrito ao repositório (variável `github_repo`). Liga a conta `deployer` ao workflow de deploy e a conta `ci` aos workflows de CI e do vigia.
- **Orçamento e cota:** o orçamento usa `google_billing_budget` e a cota diária do BigQuery usa `google_service_usage_consumer_quota_override`. Se a conta não tiver permissão para criá-los via Terraform, o README traz o passo manual.
- **Execução agendada:** Cloud Run Job e Cloud Scheduler.

### 8.3 CI/CD (GitHub Actions)

- **`ci.yml`** (em PR e push): `uv sync`, `ruff check`, `ruff format --check`, `pytest -m "not integracao"`, `dbt deps`, `dbt parse` e os testes unitários do dbt no target `ci`.
- **`deploy.yml`** (em push na branch principal):
  1. build da imagem;
  2. push para `southamerica-east1-docker.pkg.dev/<projeto>/eleitorado/pipeline:<git-sha>`;
  3. `gcloud run jobs update pipeline --image ...`.
- **`vigia.yml`** (diário, às 10:00 de Brasília): consulta `meta.execucoes` e falha se não houver, no dia, nenhuma execução de origem `agendada` com status `sucesso`. Uma retentativa bem-sucedida conta como sucesso. Na falha, o GitHub envia e-mail.
  - Isso cobre também o caso em que o job nem rodou.
  - Em repositório público, workflows agendados são desativados após 60 dias sem atividade no repositório. O README registra esse comportamento.

### 8.4 Ambiente local

- O projeto ganha uma configuração própria do gcloud (`gcloud config configurations create eleitorado`). A configuração `prod` e as credenciais ADC existentes não são alteradas sem confirmação sua.
- O projeto é sempre informado de forma explícita, pela variável `ELEITORADO_PROJETO` e pelo `project` do profile do dbt, para não depender do quota project global do ADC.
- `uv sync` cria um ambiente único com o coletor e o dbt. Os comandos rodam com `uv run coletor ...` e `uv run dbt ...`, usando `DBT_PROFILES_DIR=dbt`.
- O Terraform ainda não está instalado na máquina. A instalação será feita via winget.

### 8.5 Segredos

- A onda A não usa segredos.
- Quando forem necessários, como o token da CGU, ficam no Secret Manager e são expostos ao job como variáveis de ambiente.
- Nenhuma chave de conta de serviço é gerada. O GitHub Actions autentica por Workload Identity Federation.

## 9. Tratamento de erros

| Situação | Comportamento |
|---|---|
| Fonte fora do ar, timeout, HTTP 5xx ou 429 | 5 tentativas com espera exponencial. Se persistir, a coleta termina como `falha` e as demais seguem |
| Arquivo do dia ainda não publicado (CGU) | usa a data mais recente anunciada na página. Se for a mesma já coletada, o resultado é `sem_alteracao` |
| Conteúdo igual ao anterior | `sem_alteracao`, sem gravar original nem carregar |
| Cabeçalho mudou | carrega, marca `esquema_alterado` e destaca a mudança em `monitor_fontes` |
| Sumiu uma coluna usada no staging | o teste do dbt falha, o job termina com erro e o vigia avisa |
| Falha no meio da paginação | a coleta inteira falha e nada é carregado |
| Job não rodou (Scheduler, imagem, permissão) | o vigia avisa no mesmo dia |
| Cota diária do BigQuery atingida | as consultas falham até o dia seguinte, o job termina com erro e o vigia avisa |

## 10. Custos e travas

| Serviço | Uso estimado na onda A | Custo |
|---|---|---|
| BigQuery, armazenamento | 5 a 6 GB: CEAP e CEAPS completos, 60 dias de CEIS/CNEP, intermediate e marts | camada gratuita (10 GiB/mês) |
| BigQuery, consultas | dbt diário de 3 a 5 GB, até cerca de 150 GB/mês | camada gratuita (1 TiB/mês) |
| Cloud Run | cerca de 10 min/dia com 1 vCPU | camada gratuita, aplicada como desconto a preço Tier 1 (São Paulo é Tier 2) |
| Cloud Scheduler | 1 job | grátis (3 jobs por conta de faturamento) |
| Artifact Registry | 2 imagens, até cerca de 0,5 GB | camada gratuita (0,5 GB) |
| Cloud Storage em São Paulo (sem camada gratuita) | originais: até cerca de 6 GB por ano, em Archive após 30 dias | centavos de dólar por mês (Standard a US$ 0,035/GB, Archive a US$ 0,003/GB) |

O total esperado é de centavos de dólar por mês, coberto pelo crédito mensal de desenvolvedor. A carga histórica inicial não muda essa ordem de grandeza: os load jobs são gratuitos e o volume é de poucas centenas de MB compactados. Recarregar originais que já estão na classe Archive (`coletor recarregar`) gera uma taxa de recuperação por GB. É um uso raro e, com esses volumes, de poucos centavos.

Travas:

1. **Orçamento:** US$ 5 por mês no projeto, calculado sem créditos para mostrar o custo bruto, com alertas por e-mail em 50%, 90% e 100%.
2. **Cota personalizada do BigQuery:** 30 GiB consultados por dia no projeto, cerca de 0,9 TiB por mês. Acima disso, as consultas são bloqueadas.
3. **`maximum_bytes_billed`:** 10 GiB por consulta no profile do dbt.
4. **Limpeza automática:** expiração de 60 dias nas partições de snapshot, política de limpeza no Artifact Registry e ciclo de vida em `carga/`.

## 11. Testes do coletor

- **Fixtures:** amostras reais reduzidas de cada fonte:
  - CEAP 2008 (UTF-8 com BOM);
  - CNEP (Windows-1252);
  - página da API de deputados com `links`;
  - lista de senadores;
  - CEAPS 2008, com registros sem fornecedor;
  - amostra de municípios;
  - HTML da página de download da CGU.
- **Cobertura:**
  - validação do manifesto;
  - enumeração de competências e cálculo da legislatura atual;
  - descoberta da data da CGU a partir do HTML;
  - normalização de nomes de coluna e leitura por encoding;
  - conversão para Parquet com colunas de controle;
  - paginação `links_next` com HTTP simulado;
  - hashes e deduplicação, incluindo ZIP com metadados diferentes e mesmo conteúdo, e JSON com `Metadados.Versao` diferente;
  - escolha de partição e decorador;
  - retentativas e falha atômica.
- **Integração** (`@pytest.mark.integracao`): coleta real de um recurso pequeno (`cgu.cnep`) gravando nos datasets `_dev`. Roda sob demanda.
- A implementação segue TDD.

## 12. Riscos

1. **Histórico de sanções limitado ao período de coleta** (seção 7.5). Mitigação: começar a coleta diária o quanto antes.
2. **A descoberta da data da CGU depende do HTML da página de download.** Mitigação: fallback de D-1 a D-3 e teste com fixture.
3. **A documentação da API da Câmara a declara incompleta e sujeita a mudanças.** Mitigação: `esquema_alterado` e testes de staging.
4. **Os alertas podem ser lidos como acusação.** A web app terá de explicar que são indícios e mostrar a regra aplicada a cada um.
5. **Pré-requisitos manuais:**
   - criar o projeto GCP na conta com crédito de desenvolvedor;
   - criar o repositório no GitHub, com branch principal `main` (a branch local hoje se chama `master`);
   - instalar o Terraform.

## 13. Próximas ondas

Cada onda terá spec e plano próprios.

- **B. Executivo federal:**
  - CGU: despesas, contratos, licitações, emendas, servidores, viagens e cartões, por downloads e pela API com token;
  - Compras.gov.br e PNCP, com deduplicação entre as fontes;
  - listas de responsáveis do TCU.
- **C. Cadastros:** CNPJ da Receita Federal, com perfil e sócios de fornecedores, o que amplia os alertas.
- **D. Contas públicas e indicadores:** STN (Siconfi e transferências), IBGE Agregados, IPEA, BCB e SIORG.
- **E. Saúde, educação e previdência:** Ministério da Saúde, INEP, CAPES, ANS, ANVISA, MTE e INSS.
- **F. Geografia e justiça:** INPE (WFS) e CNJ (DataJud, condicionado às regras de reutilização).
- **TSE:** não está no levantamento. Avaliar antes da onda C, porque se encaixa no objetivo de monitoramento.
