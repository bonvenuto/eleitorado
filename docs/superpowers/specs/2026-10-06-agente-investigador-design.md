# Agente investigador (L1): design

Data: 2026-10-06
Status: aprovada; revisada depois do protótipo (seção 11 prevalece sobre o texto anterior)

## 1. Objetivo

Um agente que investiga os dados do eleitorado por conta própria em busca de **insights estratégicos**
e **situações suspeitas**, valida o que encontra (inclusive com pesquisa na internet), procura casos
correlacionados e entrega **relatórios HTML** com evidências e recursos visuais.

O agente é **L1**: recomenda, mas não decide nem age. Toda ação dele é de coleta de informação e
registro dentro da própria pasta de trabalho. O que fazer com cada achado é decisão do usuário.

### Decisões do usuário

| Tema | Decisão |
|---|---|
| Leitores dos relatórios | só o usuário (uso interno) |
| Acionamento | agendado (semanal) e sob demanda, com ou sem tema |
| Motor | Claude Code local (`claude -p`), pela assinatura do usuário, sem chave de API |
| Dados | marts e lago privado (raw, staging e intermediate, com documento completo) |
| Arquitetura | investigador + validador independente (abordagem A) |
| Ciclo operacional | laço de controle contínuo Sense-Think-Act (ReAct), explícito e auditável |

### Critério de sucesso

- Cada achado é verificável: todo número aponta para a consulta que o gerou e toda afirmação externa
  para a fonte da web, com data de acesso.
- Fato, indício e hipótese ficam separados, e a confiança segue critério fixo.
- Nenhum achado "suspeito" chega ao relatório sem passar pelo validador.
- Na avaliação com casos plantados, o agente encontra os casos e descarta a armadilha (seção 9.2).

### Fora do escopo

- Publicar, notificar terceiros ou alterar qualquer dado (o agente é L1).
- Interface web para os relatórios (o app web é outro projeto).
- Execução na nuvem ou por API paga (decisão: Claude Code local).
- Novas fontes de dados: o agente usa o que o pipeline já coleta.

## 2. Visão geral

```
                 ┌──────────────── controlador (Python, máquina de estados) ────────────────┐
 Agendador do    │ PREPARAR → EXPLORAR → INVESTIGAR ⇄ VALIDAR → CORRELACIONAR → RELATAR →  │
 Windows / CLI ─▶│ ENCERRAR       │            │          │                        │        │
                 │                ▼            ▼          ▼                        ▼        │
                 │        claude -p --agent investigador   claude -p --agent validador     │
                 │                (laço ReAct: Sense → Think → Act)                         │
                 └──────┬──────────────────┬───────────────────┬────────────────────┬──────┘
                        ▼                  ▼                   ▼                    ▼
                agente consultar     WebSearch/WebFetch   agente caderno       agente relatorio
                (DuckDB só leitura)  (hook anti-CPF)      (memória)            (HTML autocontido)
```

## 3. Componentes

O código fica num pacote novo, `agente/`, no repositório (CLI `agente`, entrada em `pyproject.toml`),
separado do `coletor`. As definições dos agentes ficam em `.claude/agents/`. Dados e relatórios ficam
fora do git: `dados/` (já ignorado) e `investigacoes/` (novo no `.gitignore`).

| Componente | Responsabilidade | Interface |
|---|---|---|
| `agente preparar` | Repete a sequência do pipeline sem a coleta: sincroniza o lago do GCS (`coletor estado restaurar`), importa os históricos para o banco e roda o dbt num target próprio (`agente`, arquivo `dados/agente.duckdb`); depois gera `investigacoes/contexto.md` (esquema e volume de cada tabela de staging, intermediate e marts, e a situação do `monitor_fontes`). | CLI |
| `agente consultar` | Executa **uma** instrução `SELECT`/`WITH` no DuckDB aberto em modo somente leitura, com tempo e linhas limitados; registra a consulta e o resumo do resultado no diário da investigação e devolve o id da consulta (`q<n>`). | CLI usada pelo agente |
| `agente caderno` | Lista, busca e registra casos e aprendizados com esquema validado. | CLI usada pelo agente |
| `agente achado` | Registra a fila de hipóteses (`hipoteses`, no EXPLORAR) e cada candidato a achado (`registrar`, estruturado) para o controlador encaminhar ao validador. | CLI usada pelo agente |
| `agente relatorio` | Valida o `relatorio.json` e gera o HTML; gera o `index.html`. | CLI |
| `agente investigar` | O controlador: máquina de estados, sessões do `claude -p`, orçamentos, retomada, captura do rastro. | CLI (entrada principal) |
| `agente hook-web` | Hook `PreToolUse` de `WebSearch`/`WebFetch`: bloqueia consulta com sequência de 11 dígitos. | stdin JSON do Claude Code; código de saída 2 bloqueia |
| `agente avaliar` | Roda o agente sobre um lago de teste com casos plantados e confere o resultado. | CLI (manual) |
| `.claude/agents/investigador.md` | Instruções do investigador: lentes de investigação, ciclo ReAct, regras de evidência, uso das ferramentas. | definição de agente do Claude Code |
| `.claude/agents/validador.md` | Instruções do validador: postura adversarial, checklist de explicações alternativas, veredito estruturado. | definição de agente do Claude Code |
| `agente/permissoes.json` | Settings do Claude Code para as sessões do agente: lista de ferramentas permitidas e o hook. | `--settings` |
| `agente/config.toml` | Orçamentos, modelo, dia e hora do agendamento. | arquivo |
| `agente/executar.ps1` | Script do Agendador do Windows: trava, `agente investigar`, notificação. | Agendador de Tarefas |

## 4. Ciclo de vida

### 4.1 Laço interno: Sense → Think → Act (ReAct)

Cada sessão do `claude -p` é um laço ReAct:

| Fase | O que acontece |
|---|---|
| **Sense** | Observa o estado: `contexto.md`, `aprendizados.md`, os casos do caderno ligados à hipótese e o resultado da última ação (linhas da consulta, página lida, veredito do validador). |
| **Think** | Atualiza a hipótese, decide a próxima ação e justifica por escrito. |
| **Act** | Executa **uma** ação de investigação: consultar, pesquisar, ler uma página, consultar o caderno, registrar um candidato ou um aprendizado. |

Em L1, **Act** só coleta informação e registra dentro de `investigacoes/<id>/`.

O rastro é capturado pelo controlador, que lê a saída `--output-format stream-json`: cada texto do
agente (Think), cada chamada de ferramenta (Act) e cada resultado (Sense) vira uma linha em
`investigacoes/<id>/ciclos.jsonl`, com a fase da máquina de estados e o carimbo de tempo. O registro
não depende de o agente lembrar de anotar.

### 4.2 Laço externo: máquina de estados do controlador

Estado persistido em `investigacoes/<id>/estado.json` depois de cada transição.

```
PREPARAR → EXPLORAR → INVESTIGAR ⇄ VALIDAR → CORRELACIONAR → RELATAR → ENCERRAR
                                   (por hipótese, em fila)
```

| Estado | Quem executa | Entrada | Saída |
|---|---|---|---|
| PREPARAR | controlador | — | lago sincronizado, `agente.duckdb`, `contexto.md`; registra a versão dos dados (commit e data do manifesto) |
| EXPLORAR | sessão do investigador | tema (opcional), alertas do pipeline, pendências e atualizações do caderno | fila de hipóteses priorizadas (`agente achado hipoteses`) |
| INVESTIGAR | uma sessão do investigador por hipótese (contexto limpo) | a hipótese, os casos ligados, os pedidos do validador da rodada anterior | candidato a achado (`agente achado registrar`) ou descarte justificado |
| VALIDAR | sessão do validador (contexto limpo, sem acesso ao raciocínio do investigador) | o candidato com as evidências | veredito estruturado: `confirmado`, `descartado` (motivo) ou `inconclusivo` (o que falta) |
| CORRELACIONAR | sessão do investigador | o achado confirmado | casos relacionados (mesma raiz de CNPJ, órgão, parlamentar, padrão repetido) anexados ao achado |
| RELATAR | controlador + uma sessão curta do investigador | achados, descartes e inconclusivos registrados | `relatorio.json` (o resumo executivo é a única parte redigida nessa sessão) e o HTML |
| ENCERRAR | controlador | resultado da investigação | caderno atualizado, `index.html` regerado, notificação |

Regras:

- **Só o controlador muda a situação de um achado**, a partir do veredito do validador. O investigador
  não consegue marcar nada como confirmado.
- `inconclusivo` volta para INVESTIGAR com os pedidos do validador, até o limite de rodadas; depois
  disso o achado fica inconclusivo e vai para o caderno como pendência.
- O validador tem as mesmas ferramentas de leitura (consultar, web, caderno), mas não registra achados.

### 4.3 Lentes de investigação (EXPLORAR)

Ponto de partida do investigador quando não há tema, nesta ordem:

1. alertas do pipeline (`alerta_*`) com casos novos desde a última investigação;
2. pendências e atualizações do caderno;
3. varreduras amplas:
   - concentração (poucos fornecedores ou favorecidos com grande parte dos valores);
   - fracionamento (contratos ou dispensas repetidos logo abaixo de limites legais);
   - saltos no tempo (picos em fim de ano ou período eleitoral);
   - valores fora da curva;
   - fornecedor novo com valores altos;
   - recorrência parlamentar-fornecedor na cota;
   - o encadeamento emenda → favorecido → contrato.

O usuário pode editar as lentes no `investigador.md`.

### 4.4 Garantias do ciclo de vida

| Garantia | Mecanismo |
|---|---|
| Orçamento | O controlador conta ciclos (chamadas de ferramenta), consultas e tempo; ao estourar, encerra a sessão e força RELATAR com o que houver. |
| Retomada | Interrupção (limite de uso da assinatura, máquina desligada, erro) deixa o estado salvo como `pausada`; a próxima execução continua da última transição concluída, sem refazer hipóteses já resolvidas. |
| Sem laço infinito | Máximo de rodadas de validação por hipótese; a mesma consulta (hash do SQL) ou a mesma busca repetida 3 vezes encerra a sessão da hipótese. |
| Encerramento com relatório | Toda investigação termina com relatório, mesmo vazio ou parcial, dizendo o que foi olhado e por que parou. |
| Exclusividade | Arquivo de trava em `investigacoes/.trava`; uma segunda execução desiste e registra o motivo. Trava com mais de 6 horas é considerada órfã. |

## 5. Ferramentas e travas (L1)

- **Somente leitura no banco:** `duckdb.connect(..., read_only=True)` e, antes de executar, a
  instrução é classificada pelo próprio DuckDB (`extract_statements`): só uma instrução, do tipo
  `SELECT`; `ATTACH`, `INSTALL`, `LOAD`, `COPY`, `PRAGMA` e `SET` são recusadas. O acesso a
  arquivos fica restrito pelo próprio DuckDB: `enable_external_access = false` com
  `allowed_directories` apenas para o lago (`dados/raw`, `dados/meta`) e os marts (`dados/publico`),
  que as views do staging e dos marts leem. Qualquer `read_*` ou `glob` fora deles falha. Os dois
  ajustes são feitos com `SET` na conexão antes da primeira consulta (nessa ordem) e não podem ser
  desfeitos por ela (verificado no DuckDB 1.5.6). A checagem do tipo da instrução continua necessária:
  com o acesso restrito, um `COPY` para dentro de um diretório permitido ainda seria aceito.
- **Limites da consulta:** tempo máximo (padrão 60 s), até 200 linhas exibidas ao agente (com a
  contagem total) e o resultado completo salvo em Parquet no diário para o relatório.
- **Permissões das sessões** (`agente/permissoes.json`, modo sem perguntas: o que não está liberado é
  negado):
  - `Bash(uv run agente consultar:*)`, `Bash(uv run agente caderno:*)`, `Bash(uv run agente achado:*)`;
  - `Read` de `investigacoes/contexto.md`, `investigacoes/caderno/` e `investigacoes/<id>/`; `Write`
    só em `investigacoes/<id>/`;
  - `WebSearch`, `WebFetch`.

  Tudo o mais é negado: outros comandos, git, gcloud, terraform e edição fora da pasta.
- **Hook anti-CPF:** `PreToolUse` em `WebSearch` e `WebFetch` bloqueia texto com 11 dígitos seguidos
  (com ou sem pontuação). CNPJ (14) e nomes passam. Nenhum CPF sai da máquina numa busca.
- **Conteúdo externo é dado, nunca instrução:** páginas da web e campos de texto livre das fontes. A
  instrução está nos dois agentes; o efeito de uma injeção fica contido porque não há ferramenta com
  efeito fora da pasta da investigação.
- **Privacidade:** `investigacoes/` fica fora do git. O HTML mascara todo CPF (inclusive em texto);
  o documento completo só aparece nos resultados das consultas, no diário local.

## 6. Relatório

### 6.1 `relatorio.json` (validado pelo gerador)

O gerador **recusa** gerar o HTML quando:

- um achado não tem evidência;
- um número citado não referencia uma consulta (`q<n>`) do diário;
- uma fonte da web não tem URL e data de acesso;
- um achado `situação suspeita` não tem veredito `confirmado` do validador.

Cada achado tem:

- tipo: `insight estratégico`, `situação suspeita` ou `qualidade de dado`;
- título e confiança;
- **fatos** (o que os dados mostram), **indícios** (o que pode indicar) e **hipóteses** (o que não se
  sabe);
- explicações alternativas testadas pelo validador;
- evidências (consultas, gráficos, fontes da web);
- correlacionados;
- recomendações L1 (o que o usuário pode fazer).

**Confiança** (critério fixo):

- **alta**: confirmado pelo validador e corroborado por fonte independente (dado e fonte oficial na
  web);
- **média**: confirmado só com os dados.

Inconclusivos e descartados vão em seções próprias.

### 6.2 HTML

Arquivo único e autocontido: Vega-Lite e vega-embed embutidos, abre sem internet. Tema claro e escuro;
versão para impressão. Seções:

1. Cabeçalho: tema, data, versão dos dados, situação (completo ou parcial, e por quê), orçamento usado.
2. Resumo executivo: cartões de números-chave e a lista dos achados com selos de tipo e confiança.
3. Achados.
4. Inconclusivos.
5. Descartados.
6. Apêndices: consultas (SQL, linhas, hash do resultado), fontes da web (URL, data de acesso,
   trecho), linha do tempo dos ciclos Sense-Think-Act, limitações dos dados.

Todo número do texto liga para a sua consulta no apêndice.

### 6.3 Catálogo visual

O agente escolhe o tipo e aponta a consulta; o gerador monta o gráfico com cores e acessibilidade
padronizadas.

| Para mostrar | Visual |
|---|---|
| Concentração | ranking em barras horizontais |
| Evolução e saltos | linha no tempo com o evento marcado |
| Fora do padrão | dispersão ou distribuição com o caso destacado |
| Relações (empresa, órgão, parlamentar) | grafo de rede (SVG gerado pelo gerador) |
| Números-chave | cartões |
| Detalhe | tabela com os registros de origem |

### 6.4 Índice

`investigacoes/index.html`: todas as investigações (data, tema, situação, número de achados) e o
caderno de casos por situação.

## 7. Memória: caderno de casos

Fica em `investigacoes/caderno/`: um JSON por caso e um índice.

| Campo | Conteúdo |
|---|---|
| `caso_id` | hash estável do tipo de padrão e das entidades (ordenadas) |
| título, tipo | |
| entidades | raiz de CNPJ e CNPJ, órgão/UG, `parlamentar_id`, emenda, contrato |
| situação | `aberto`, `inconclusivo`, `confirmado`, `descartado` |
| confiança | para confirmados |
| histórico | por investigação: data, veredito, resumo, link do relatório |
| consultas-chave | SQL que sustenta o caso, com o resumo do resultado na última execução |
| gatilho de revisão | recurso cuja atualização reabre o caso, ou data |

Regras:

- Antes de investigar uma hipótese, o agente consulta o caderno (`agente caderno buscar`).
- Caso **descartado** só reabre se a versão dos dados das fontes envolvidas mudou depois do descarte
  (o controlador compara).
- Em PREPARAR, o controlador reexecuta as consultas-chave dos casos **confirmados**. Mudança relevante
  (linhas novas ou variação de valor acima de 10%) põe o caso na fila do EXPLORAR como atualização.
- **Inconclusivos** entram na fila com prioridade, com o que faltava checar.
- O agente escreve no caderno só pela ferramenta, com esquema validado.

**Aprendizados** (`caderno/aprendizados.md`): peculiaridades dos dados que evitam erros repetidos (ex.:
`CODIGO_CAMARA` não é CNPJ; o Senado publica CPF mascarado; `dim_autor_emenda` tem homônimos;
licitações só até 2024-04). O agente propõe pela ferramenta; cada aprendizado traz a investigação de
origem. Nada vindo da web vira aprendizado. O arquivo é do usuário para revisar e editar, e o agente o
lê no início de cada sessão.

Nada expira; o backup de `investigacoes/` é do usuário.

## 8. Operação

- **Agendado:** tarefa do Agendador do Windows, segunda-feira às 09:00 (depois do pipeline das
  07:30), com "executar assim que possível se perdida". Roda `agente\executar.ps1`.
- **Sob demanda:** `uv run agente investigar --tema "..."`; sem `--tema`, investigação livre.
- **Fim da execução:** notificação do Windows (toast nativo via PowerShell, sem dependência) com o
  número de achados e o caminho do relatório.
- **Autenticação:** `claude -p` usa o login do Claude Code do usuário; `preparar` usa as credenciais
  do GCS do `.env`. Nenhuma chave nova.
- **Modelo:** o padrão do Claude Code do usuário, configurável em `agente/config.toml`.
- **Orçamentos padrão** (`agente/config.toml`):

| Modo | Ciclos | Tempo | Hipóteses aprofundadas | Rodadas de validação |
|---|---|---|---|---|
| Livre | 60 | 90 min | até 5 | 2 |
| Com tema | 40 | 60 min | até 3 | 2 |

- **Recursos:** lago ~500 MB, `agente.duckdb` ~1,5 GB; PREPARAR leva ~10 min (sincronização
  incremental e dbt).

## 9. Testes

### 9.1 Unitários (pytest, no CI, sem chamar o Claude)

- **consultar:** recusa `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `ATTACH`, `INSTALL`, `LOAD`, `COPY`,
  `PRAGMA`, `SET`, várias instruções e leitura de arquivo fora do lago; respeita somente leitura,
  tempo e limite de linhas; grava o diário e devolve `q<n>`.
- **hook-web:** bloqueia 11 dígitos (com e sem pontuação); deixa passar CNPJ e texto comum.
- **gerador:** recusa os quatro casos da seção 6.1; mascara CPF em todo texto; o HTML não referencia
  recurso externo; todo número tem link para a consulta.
- **caderno:** `caso_id` estável para as mesmas entidades em outra ordem; deduplicação; regras de
  reabertura de descartados; gatilho de atualização de confirmados.
- **controlador:** transições da máquina de estados; só o veredito do validador confirma; estouro de
  orçamento força RELATAR; retomada depois de interrupção em cada estado; detecção de repetição;
  trava exclusiva e trava órfã. Usa um executor falso no lugar do `claude -p`, que devolve saídas
  `stream-json` gravadas.

### 9.2 Avaliação (manual: `uv run agente avaliar`)

Lago de teste pequeno, com casos plantados:

- empresa sancionada recebendo pagamentos de emenda na vigência da sanção (deve ser confirmada);
- fornecedor de cota com valor muito fora da curva (deve aparecer como achado);
- armadilha de homônimo: dois parlamentares com o mesmo nome e um alerta aparente que se desfaz ao
  olhar o `parlamentar_id` (o validador deve descartar).

A avaliação passa se os dois casos aparecem e a armadilha é descartada. Deve ser rodada ao mudar as
instruções dos agentes; consome a assinatura, por isso não roda no CI.

## 10. Riscos

| Risco | Mitigação |
|---|---|
| Viés de confirmação (o agente "acha" o que procura) | validador independente e adversarial; critério de confiança fixo; seção de descartados |
| Falso positivo grave (acusar alguém sem base) | relatório interno; fato, indício e hipótese separados; nada "suspeito" sem validação |
| Vazamento de CPF | hook na web; máscara no HTML; `investigacoes/` fora do git |
| Injeção de instrução por página web ou texto da fonte | conteúdo externo tratado como dado; ferramentas sem efeito fora da pasta |
| Limite de uso da assinatura | orçamentos; estado `pausada` e retomada |
| Custo de tempo do PREPARAR | sincronização incremental; dbt só quando o lago mudou |
| Consulta pesada travando a máquina | tempo máximo por consulta; limite de memória do DuckDB (4 GB, como o profile) |

## 11. Revisões depois do protótipo (2026-10-06)

O protótipo (branch `proto/agente`) foi executado de ponta a ponta com o `claude -p` real, o lago de
produção e o banco local. Estas decisões substituem o texto anterior onde houver conflito.

1. **Ferramentas do agente por MCP, sem shell.** No modo `dontAsk`, o Claude Code libera sozinho
   comandos que considera só de leitura (`ls`, `cat`...): com `Bash` disponível, o agente leria
   qualquer arquivo da máquina, inclusive credenciais. As ferramentas (consultar, caderno,
   hipóteses, achados, veredito, resumo) passam a ser um servidor MCP em Python
   (`agente/servidor.py`, `python -m agente.servidor`), e os agentes só têm essas ferramentas,
   `WebSearch` e `WebFetch`. Não há `Bash`, `Read` nem `Write`. O servidor expõe só as ferramentas
   do papel (investigador ou validador) e recusa escrita fora da fase e do alvo da sessão, que o
   controlador passa por variáveis de ambiente. Os comandos `agente consultar/caderno/achado/
   hook-web` da seção 3 não existem; o hook é `python -m agente.hook_web`.
2. **Mensagens de erro ao agente:** só exceções `ToolError` do MCP chegam ao cliente com a
   mensagem; o servidor usa `ErroFerramenta(ToolError)` para o agente poder corrigir.
3. **O validador registra o veredito** pela ferramenta `veredito_registrar` (estruturado). Ele
   continua sem poder registrar achados.
4. **Valores só nos fatos:** título, indícios, hipóteses e recomendações de um achado não podem ter
   R$, porcentagem ou número com 3 ou mais dígitos (anos e números de lei não contam). É a forma de
   garantir que todo número do relatório aponte para uma consulta.
5. **Reabertura de casos:** confirmados e descartados são reabertos quando o resultado das
   consultas-chave muda (linhas ou soma das colunas numéricas com variação acima de 10%). Isso
   substitui a comparação por versão das fontes, que o lago não registra por caso.
6. **Views particionadas:** o dbt-duckdb cria as views dos marts particionados sem
   `hive_partitioning`, e as colunas de partição (`casa`, `ano`...) somem. O `preparar` recria essas
   views no banco do agente.
7. **Recursos reais:** lago local com cerca de 4 GB (`dados-agente/`, com o `agente.duckdb` de
   3 GB); a primeira preparação levou cerca de 7 minutos.
8. **Agendamento:** dia e hora são parâmetros de `agente/agendar.ps1` (padrão segunda, 09:00), não
   do `config.toml`.
9. **Avaliação:** a armadilha de homônimo usa uma empresa com o mesmo nome de uma sancionada e
   outro CNPJ (não pode ser confirmada), além de dois parlamentares com o mesmo nome. A avaliação
   usa um `config.toml` próprio (`avaliacao/`), para não tocar no lago real. Os dados são fictícios mas verossímeis
   (nomes plausíveis, CNPJs com dígitos verificadores válidos) e o contexto avisa o agente de que
   é uma avaliação: na primeira rodada real, com nomes genéricos e CNPJs inválidos, o agente
   concluiu, com razão, que a base era de teste e descartou os casos. A armadilha só falha se o homônimo for
   confirmado como situação suspeita: apontá-lo como problema de qualidade de dado ("mesmo nome,
   CNPJ diferente") é o comportamento correto, e foi o que o agente fez na avaliação real.
12. **Avaliação real (terceira rodada):** os três critérios passaram, com 104 ciclos, 71 consultas,
    11 sessões e 24 minutos.
10. **Relatório recusado:** se a validação do relatório falhar, a investigação termina `parcial`,
    com o motivo em `relatorio-recusado.txt`.
11. **Orçamento medido na avaliação real:** explorar gasta cerca de 13 ciclos e cada hipótese
    cerca de 25 (investigar, validar, correlacionar). Os padrões passam a 120 ciclos (livre) e 80
    (tema). Uma hipótese nova só começa com pelo menos 20 ciclos sobrando; a validação de um achado
    já registrado sempre roda, com no mínimo 12 ciclos, mesmo que passe do orçamento; o resumo
    executivo sempre é escrito (até 6 ciclos).
