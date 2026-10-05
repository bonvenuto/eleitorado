# Onda B: emendas parlamentares, contratos e licitações federais

**Data:** 2026-10-05
**Status:** aprovado em conversa, aguardando revisão da spec escrita
**Base:** a arquitetura da [migração para DuckDB](2026-10-04-migracao-duckdb-design.md): coletor, lago em Parquet, dbt-duckdb e publicação no R2. As regras de coleta, de modelagem e de LGPD da [spec da onda A](2026-10-03-ingestao-onda-a-design.md) continuam valendo.

## 1. Objetivo

Acrescentar ao repositório:
- as emendas parlamentares, que ligam os parlamentares da onda A ao destino do dinheiro;
- os contratos e as licitações do Executivo federal.

Com isso, as sanções que já temos (CEIS e CNEP) cruzam com três novos tipos de gasto público.

**Fica fora desta onda:**
- CNPJ da Receita (próxima onda, com desenho de volume próprio);
- execução completa de despesas;
- servidores, viagens e cartões;
- contratações (licitações) do PNCP depois de abril de 2024;
- modelagem de estados e municípios. O raw do PNCP guarda todas as esferas, mas só o federal é modelado agora.

**Critérios de sucesso:**
- os recursos novos são coletados todo dia pelo `pipeline.yml`, com a carga histórica completa;
- os marts novos e os três alertas novos são publicados no R2, com o teste `sem_cpf_completo` em todos;
- o `monitor_fontes` e o `alerta_fonte_reduzida` cobrem as fontes novas sem código extra;
- o uso do GitHub Actions fica abaixo de 2.000 minutos por mês, e o R2 abaixo de 10 GB.

## 2. Etapas

| Etapa | Conteúdo | Plano |
|---|---|---|
| **B1** | Portal da Transparência: emendas (4 recursos), contratos e licitações federais (3 recursos), modelos e alertas | Plano 6 |
| **B2** | PNCP: contratos de todas as esferas no raw, unificação com os contratos federais da B1 | Plano 7 |

A B1 não depende da B2. A B2 estende o `fct_contrato_federal` da B1.

## 3. Fontes (verificadas em 05/10/2026)

### 3.1 Portal da Transparência (B1)

O padrão é o mesmo do CEIS e do CNEP: a página `download-de-dados/<base>` lista no JavaScript as competências disponíveis, e o arquivo fica em `download-de-dados/<base>/<competência>`. Os zips têm CSV em Latin-1, separados por `;`.

| Recurso | Arquivo | Competência | Escopo | Volume |
|---|---|---|---|---|
| `cgu.emendas` | `emendas-parlamentares/UNICO`, `EmendasParlamentares.csv` (28 colunas) | snapshot | 2014 em diante | 94 mil linhas |
| `cgu.emendas_convenios` | mesmo zip, `EmendasParlamentares_Convenios.csv` (12 colunas) | snapshot | | 85 mil |
| `cgu.emendas_favorecidos` | mesmo zip, `EmendasParlamentares_PorFavorecido.csv` (13 colunas) | snapshot | | 826 mil |
| `cgu.emendas_documentos` | `emendas-parlamentares-documentos/AAAA`, `AAAA_EmendasParlamentares_PorDocumento.csv` (48 colunas) | ano | 2014 em diante | cerca de 300 mil por ano |
| `cgu.contratos` | `compras/AAAAMM`, `AAAAMM_Compras.csv` (24 colunas) | mês | 2013-01 em diante | cerca de 2 mil por mês |
| `cgu.licitacoes` | `licitacoes/AAAAMM`, `AAAAMM_Licitação.csv` (17 colunas) | mês | 2013-01 a 2024-04 (série encerrada) | cerca de 700 por mês |
| `cgu.licitacoes_participantes` | mesmo zip, `AAAAMM_ParticipantesLicitação.csv` (13 colunas) | mês | 2013-01 a 2024-04 | cerca de 40 mil por mês |

**Documentos:**
- emendas: CPF de favorecido já vem mascarado pela fonte, e o CNPJ vem completo;
- contratos e licitações: CPF e CNPJ vêm completos. O sigilo legal aparece como `-11` / `Sigiloso`.

**Cadências:**
- as emendas (snapshot) são semanais;
- documentos de emendas: o ano corrente é semanal e os anteriores, mensais;
- contratos: os dois meses mais recentes são semanais e os anteriores, mensais;
- licitações: mensal. Como a série terminou, as competências depois de 2024-04 não são agendadas.

### 3.2 PNCP (B2)

- **API de Consultas:** `https://pncp.gov.br/api/consulta/v1/`, pública e sem token.
- **`GET /contratos`:** usa `dataInicial` e `dataFinal` (`AAAAMMDD`) e `pagina`, e aceita `tamanhoPagina` até 500.
- **`GET /contratos/atualizacao`:** tem os mesmos parâmetros, mas filtra pela data de atualização.
- **Volume:** cerca de 175 mil contratos por mês de todas as esferas, 11% federais. Não há filtro por esfera; o registro traz `orgaoEntidade.esferaId` e `poderId`.
- **Chave:** `numeroControlePNCP`. A compra vinculada vem em `numeroControlePncpCompra`.
- **Limite de requisições:** depois de 5 a 7 requisições seguidas, responde `HTTP 429` com um corpo HTML; uma pausa de cerca de 5 s libera.
- **Documentos:** CPF e CNPJ do fornecedor vêm completos.

## 4. Coletor

### 4.1 B1

- **Competência mensal:** `Competencia.de_mes(ano, mes)`, com o rótulo `AAAA-MM`, e o tipo de competência `mes` no manifesto. A agenda gera as competências mensais desde `competencia.inicio` até o mês corrente, ou até `competencia.fim` quando informado. `fim` é um campo novo, opcional, para séries encerradas.
- **Arquivo dentro do zip:** `formato.arquivo_no_zip`, um padrão glob como `*_Compras.csv` ou `EmendasParlamentares.csv`. Quando o zip tem um só CSV, o comportamento atual não muda.
- **Página de competências:** o adaptador de arquivos já lê a lista de datas da página do CEIS e do CNEP; ele é generalizado para a lista de competências mensais e anuais e para `UNICO`. Um recurso que não está publicado (`HTTP 403` ou `404`) recebe o status `nao_publicada`, sem gerar falha.
- **Partição no lago:** a de mês é `AAAAMM`, e o `Particionamento` ganha a granularidade `MONTH`.
- **Recursos que vêm do mesmo zip:** cada um baixa o arquivo, e a deduplicação por hash vale para cada um. São 32 MB por semana a mais para as emendas, o que é aceitável. Compartilhar o download fica para depois.

### 4.2 B2

**Adaptador `api_paginada`:** percorre `pagina` de 1 até `totalPaginas`, com estes parâmetros no manifesto:
- `tamanhoPagina`;
- os campos de período;
- uma pausa mínima entre requisições, de 1,5 s;
- um teto de páginas por execução.

**Limite de requisições:** um `429` provoca espera e nova tentativa (5 s, depois 10 s e 20 s), até 5 vezes por página. O cliente HTTP ganha esse tratamento genérico para `429`.

**Recursos:**
- **`pncp.contratos`:** um por mês, de 2021-01 em diante, com o registro inteiro guardado como JSON, como já é feito com o Senado;
- **`pncp.contratos_atualizacao`:** snapshot diário com os contratos atualizados no dia anterior.

**Carga histórica parcelada:**
- cada execução coleta no máximo `limite_competencias_por_execucao` meses pendentes do PNCP (2 por padrão), do mais recente para o mais antigo;
- um mês que falhou fica pendente para a execução seguinte.

**Cadências:**
- o mês corrente é recoletado inteiro uma vez por semana, e os meses anteriores, uma vez por mês;
- as retificações chegam pelo `contratos_atualizacao`, diariamente.

## 5. Modelagem

### 5.1 Staging

- Um modelo `stg_cgu__<recurso>` por recurso, usando as macros já existentes: `data_br`, `numero_br`, `normalizar_documento` e `texto`.
- `stg_pncp__contratos` une os meses e as atualizações e fica com a versão mais recente de cada `numeroControlePNCP`, pela data de atualização do registro.

### 5.2 Marts (B1)

**`dim_autor_emenda`:** uma linha por autor de emenda (código e nome).
- O `parlamentar_id` é preenchido quando o nome normalizado (sem acentos, maiúsculas, espaços simples) corresponde a exatamente um parlamentar do `dim_parlamentar`.
- `tipo_autor` diferencia `parlamentar`, `bancada`, `comissao`, `relator` e `outro`, pelo tipo de emenda.

**`fct_emenda`:** uma linha por emenda.
- Identificação e autor: código da emenda, ano, número, autor e tipo.
- Classificação: função e subfunção.
- Destino: o local de aplicação, com o código IBGE do município (que liga ao `dim_municipio`) e a UF.
- Valores: empenhado, liquidado, pago e restos a pagar.

**`fct_emenda_favorecido`:** uma linha por favorecido e emenda.
- O documento sai como a fonte publica: CNPJ completo, ou CPF já mascarado.
- Inclui `documento_tipo`, a raiz do CNPJ e o valor recebido.

**`fct_emenda_pagamento`:** uma linha por documento de pagamento, com data, fase, favorecido e valor.

**`fct_contrato_federal`:** uma linha por contrato.
- A chave da B1 é `cgu:<código UG>:<número do contrato>`.
- Inclui órgão, UG, objeto, modalidade, datas de assinatura, publicação e vigência, e os valores inicial e final.
- O fornecedor sai normalizado: CNPJ, raiz, ou CPF mascarado.
- Inclui o vínculo com a licitação.

**`fct_licitacao_federal`:** uma licitação por (UG, modalidade, número), de 2013 a 2024-04.

**`fct_licitacao_participante`:** participante, marca de vencedor e documento normalizado.

### 5.3 Alertas (B1)

Os três alertas usam a chave de correspondência do alerta da cota (`cpf:<doc>` ou `cnpj:<raiz>`) e qualquer versão já vista da sanção, desde que vigente na data relevante:

| Alerta | Data relevante | Grão |
|---|---|---|
| `alerta_contrato_fornecedor_sancionado` | assinatura do contrato | contrato × sanção |
| `alerta_licitacao_vencedor_sancionado` | data de abertura (ou de resultado) da licitação; só participantes vencedores | participação × sanção |
| `alerta_emenda_favorecido_sancionado` | data do documento de pagamento | pagamento × sanção |

Cada alerta tem `alerta_id`, as colunas resumidas dos dois lados, `tipo_correspondencia`, `regra` e os `_coleta_id` de origem. O aviso de interpretação é o mesmo de antes: é um indício para investigar, não a constatação de irregularidade.

### 5.4 B2

O `fct_contrato_federal` passa a unir o Portal e o PNCP.
- O PNCP entra só com a esfera federal (`F`) e o poder Executivo (`E`).
- **Pareamento:** UG mais número do contrato normalizado (só dígitos, sem zeros à esquerda) mais ano.
- **Quando há par:** vale o PNCP, com a chave `pncp:<numeroControlePNCP>`, e a chave do Portal fica em `id_cgu`.
- **Taxa de pareamento:** um teste de aviso (`warn`) dispara se, nos anos em que as duas fontes se sobrepõem, menos de 50% dos contratos do PNCP encontrarem par.

## 6. Publicação e testes

- Os marts novos entram em `marts/` no R2. Os grandes ficam particionados por ano: `fct_emenda_pagamento` e `fct_licitacao_participante`.
- O teste `sem_cpf_completo` roda em todos os marts novos. O `numero_contrato`, os números de processo e de documento e as URLs entram na lista de exclusões, quando houver.
- **Testes unitários do dbt:**
  - a correspondência de autores (homônimo, bancada, um único candidato);
  - os três alertas (vigência, raiz do CNPJ, CPF, versão de exclusão);
  - a versão mais recente no PNCP;
  - o pareamento Portal × PNCP.
- **Testes Python:**
  - competência mensal com início e fim;
  - `arquivo_no_zip`;
  - competência não publicada;
  - no adaptador paginado: `429` com espera, teto de páginas e retomada da carga histórica.
- `dbt/tests/lago_vazio/esquemas.json` ganha os esquemas das fontes novas, gerados de um lago real com `scripts/lago_vazio.py --de-lago`.

## 7. Custos e limites

| Item | Estimativa |
|---|---|
| Raw novo no GCS | B1 abaixo de 1 GB; PNCP com todas as esferas, cerca de 4 GB. Ao todo, cerca de R$ 0,50 por mês |
| Cache do Actions | o lago chega a cerca de 5 GB (o limite é 10 GB) |
| R2 | cerca de 1 GB a mais (total de cerca de 1,3 GB) |
| Minutos do Actions | carga histórica da B2: cerca de 30 minutos a mais por dia, durante uns 30 dias; depois, 1.200 a 1.400 minutos por mês ao todo |

## 8. Efeito na virada (Plano 5)

As fontes novas nascem sob `paralelo/`. Por isso, a virada passa a **promover `paralelo/` para a raiz** do bucket, copiando os objetos e trocando o prefixo do workflow para vazio, em vez de reconstruir o raw a partir dos originais da raiz. Assim ela não depende de as fontes ainda publicarem arquivos antigos. A seção 8.3 da spec da migração é atualizada quando o Plano 5 for escrito.

## 9. Riscos

| Risco | Mitigação |
|---|---|
| A Câmara e o Portal reprocessam o histórico (como a CEAP em 05/10) | `alerta_fonte_reduzida`; os originais de todas as versões ficam arquivados |
| Homônimos na ligação autor × parlamentar | só se liga quando há exatamente um candidato; teste da taxa de ligação; o mart mostra os autores sem ligação |
| Limite de requisições do PNCP mais rígido que o observado | espera progressiva; teto de páginas por execução; carga histórica retomável |
| Pareamento Portal × PNCP fraco | teste de aviso com a taxa de pareamento; as duas chaves ficam no mart para auditoria |
| CPF completo em contratos e licitações | só no lago privado; mascarado nos marts; `sem_cpf_completo` em todos os marts |
