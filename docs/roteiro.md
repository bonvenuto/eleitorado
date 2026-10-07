# Roteiro

O que falta fazer, em ordem de prioridade. Cada item traz o contexto para quem pegar o trabalho
(pessoa ou agente) começar sem depender de conversas anteriores. Regras e fluxo de trabalho:
[AGENTS.md](../AGENTS.md). Atualize este arquivo no mesmo PR que conclui ou muda um item.

Estado em 2026-10-07.

## Feito

| Onda | O que trouxe | Spec | Plano |
|---|---|---|---|
| A | Câmara e Senado (parlamentares e cota), CGU (CEIS, CNEP), IBGE; coletor, lago, dbt | `2026-10-03-ingestao-onda-a-design.md` | planos 1 a 3 |
| Migração | BigQuery → DuckDB no GitHub Actions, marts no R2 | `2026-10-04-migracao-duckdb-design.md` | plano 4 (virada concluída) |
| B1 | Emendas, contratos e licitações do Portal da Transparência | `2026-10-05-onda-b-emendas-contratos-design.md` | plano 6 |
| B2 | Contratos do PNCP, unificados aos do Portal | idem | plano 7 |
| Agente | Investigador L1 com validador, caderno de casos e relatórios HTML | `2026-10-06-agente-investigador-design.md` | plano 8 |
| Qualidade | `valor_suspeito` nos contratos, `data_emissao_valida` na cota | — | PR #30 |
| C1 | Base do CNPJ da Receita, `dim_empresa`, `dim_estabelecimento` e 4 alertas | `2026-10-06-onda-c1-receita-cnpj-design.md` | plano 9 |

## 1. Fechar a onda C1 (em andamento)

O código está na `main` (PR #33). A primeira coleta pelo GitHub Actions falhou: a Receita
derruba a conexão de IPs do GitHub (todas as URLs, inclusive a página web; diagnóstico no PR
#35). A coleta passou a rodar do computador do mantenedor (`scripts/receita_local.ps1`); o
detalhe de deputados funciona do GitHub e foi para o pipeline diário (cadência mensal).

- [ ] Primeira coleta local: linhas mantidas por grupo (esperado: ~250 mil empresas, ~657 mil
  estabelecimentos, ~388 mil sócios, ~159 mil no Simples), tempo (~50 min no protótipo) e o
  envio ao bucket.
- [ ] **Usuário:** agendar a coleta (`.\scripts\agendar_receita.ps1`, segundas às 02:00).
- [ ] Se o computador ficar desligado mais de 40 dias, o `monitor_fontes` acusa atraso e o
  pipeline deixa de publicar. Avaliar uma alternativa fora da máquina local (job ou runner
  em São Paulo, se os IPs do Google não forem bloqueados) se isso virar problema.
- [ ] No pipeline diário seguinte: `dim_empresa`, `dim_estabelecimento` e os 4 alertas publicados
  no R2; números dos alertas perto dos da spec, seção 10.
- [ ] Rodar o `preparar` do agente e a avaliação (`uv run agente avaliar`) com o caso plantado novo
  (BETA ENGENHARIA, empresa baixada recebendo emenda, que deve ser confirmado).

## 2. Falha diária: licitações da CGU de 2018-12

O ZIP `cgu.licitacoes` da competência 2018-12 vem truncado na própria fonte (8 MiB, `BadZipFile`).
A coleta falha todo dia e o `pipeline.yml` termina com saída 3 (os marts são publicados, mas o job
fica vermelho e esconde falhas novas).

Opções: (a) um campo no manifesto para competências conhecidamente quebradas, que o agendador
pula e o `monitor_fontes` mostra; (b) tratar `BadZipFile` de competência antiga como estado
próprio (`fonte_corrompida`), sem contar como falha. A (a) é explícita e reversível; recomendada.
Antes, conferir se a CGU já corrigiu o arquivo.

## 3. Onda C2: dados eleitorais do TSE

Candidaturas, bens declarados, receitas (doações) e despesas de campanha, para cruzar com cota,
emendas, contratos e a Receita (C1). Precisa de sondagem e spec próprias, no mesmo fluxo da C1
(protótipo com dados reais antes do plano).

- **Fonte:** Portal de Dados Abertos do TSE (`dadosabertos.tse.jus.br`, CKAN), arquivos por
  eleição (`consulta_cand_AAAA`, `bem_candidato_AAAA`, prestação de contas de candidatos com
  receitas e despesas). **O domínio é `.jus.br`**, fora dos hosts permitidos do coletor: incluir
  `.jus.br` em `SUFIXOS_OFICIAIS` é decisão do usuário.
- **A verificar na sondagem:** quais eleições (2018, 2020, 2022, 2024), tamanho dos arquivos, como
  o TSE publica hoje o CPF de candidatos e de doadores (completo, mascarado ou ausente) e como
  ligar o candidato ao `parlamentar_id` (nome de urna e CPF; para deputados, o CPF do detalhe da
  Câmara está no lago privado).
- **Cruzamentos pretendidos:** doador de campanha que vira fornecedor da cota, contratado ou
  favorecido de emenda do mesmo parlamentar; empresa doadora ou fornecedora de campanha com sócio
  ligado ao parlamentar (sócios da C1); evolução patrimonial entre eleições; despesa de campanha
  com empresa irregular ou recém-aberta (alertas da C1).
- **LGPD:** doador pessoa física e CPF ficam no lago privado; os marts trazem só agregados ou a
  máscara.

## 4. Licitações do PNCP

As licitações do Portal da Transparência vão só até 2024-04; desde então as compras estão no PNCP,
do qual hoje coletamos só os contratos (onda B2). Sem as licitações (e os participantes) do PNCP,
o `alerta_licitacao_socios_em_comum` e o `alerta_licitacao_vencedor_sancionado` só olham
licitações antigas. Investigar a API de consulta do PNCP (contratações publicadas e, se houver,
participantes/propostas) e o volume.

## 5. Novas fontes (do mapeamento)

Do [mapeamento de fontes](mapeamento-dados-publicos.md), as que mais acrescentam aos cruzamentos
atuais:

- **Transferegov (MGI):** convênios e transferências; liga a emenda à execução no município (o elo
  que falta em emenda → favorecido → contrato).
- **TCU:** responsáveis com contas julgadas irregulares, inabilitados e inidôneos; cruzar com
  fornecedores, sócios e favorecidos, como já fazemos com CEIS/CNEP.
- **Siconfi (Tesouro Nacional):** finanças dos municípios que recebem emendas.

## 6. Pendências operacionais

- [ ] **Dependabot:** PRs #13 a #17 (versões maiores das ações e `google-cloud-storage`). Ao
  atualizar uma ação, atualizar o SHA nos dois workflows (`pipeline.yml` e `ci.yml`).
- [ ] **Usuário:** agendar o agente semanal (`.\agente\agendar.ps1`).
- [ ] **Usuário:** desativar no GCP as APIs que não usamos mais desde a migração (Cloud Run, Cloud
  Scheduler, Artifact Registry, BigQuery).

## 7. Agente investigador

- [ ] Decidir o modelo (hoje usa o padrão da conta, Sonnet, porque `--setting-sources project`
  ignora o `model` do usuário); comparar com Opus na avaliação.
- [ ] Hipóteses que não couberam no orçamento devem ir para o caderno de casos como pendências.
- [ ] A trilha "Think" do relatório às vezes sai vazia: investigar o registro do raciocínio por
  ciclo.

## 8. Produto público

Spec em `docs/superpowers/specs/2026-10-07-site-publico-design.md`. Plano 10 (dados do site:
modelos `site_*`, `coletor site`, publicação incremental) em
`docs/superpowers/plans/2026-10-07-plano-10-dados-do-site.md`; plano 11 (frontend em `site/`,
Cloudflare Pages) em `docs/superpowers/plans/2026-10-07-plano-11-frontend-do-site.md`.
**Usuário:** criar o projeto no Cloudflare Pages, a regra de CORS do bucket R2 (spec, seção 9)
e decidir se o job `site` do CI entra no ruleset da `main`.
