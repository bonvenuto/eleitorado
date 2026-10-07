# Plano 10: dados do site público

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** o pipeline diário passa a gerar e publicar no R2 (`site/`) os arquivos JSON que o site
público lê: resumo da capa, índice de busca, um arquivo por parlamentar, empresas em blocos e
alertas paginados.

**Architecture:** modelos dbt `site_*` (pasta `dbt/models/site/`, só leem marts e seeds) montam
cada arquivo em SQL, uma linha por arquivo (`caminho`, `conteudo`). O comando novo
`coletor site` confere cada arquivo (caminho, tamanho, CPF completo nos textos, JSON Schema) e
grava em gzip em `publico/site/`; o `coletor publicar` passa a aceitar `site/`, a enviar só o que
mudou (MD5 × ETag do R2) e a mandar o site com `Content-Encoding: gzip`. O contrato com o
frontend (plano 11) são os JSON Schemas de `site/esquemas/` e os exemplos de `site/exemplos/`.

**Tech Stack:** dbt-duckdb 1.12 (DuckDB 1.5), Python 3.12 (uv), `jsonschema` (nova dependência),
boto3 (R2), GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-07-site-publico-design.md` (seções 4, 5, 7, 8 e 11).

## Global Constraints

- Código, comentários, docs e commits em português; linhas de até 100 colunas (`ruff`).
- Trabalhe no branch `feat/site-dados`, criado a partir da `main`. Nunca commite na `main`.
- Não faça merge, não dispare workflow (`gh workflow run`) e não mexa em secrets sem o ok do
  usuário.
- Modelos `site_*` leem **só marts e seeds** (`ref` de `dim_*`, `fct_*`, `alerta_*`,
  `monitor_fontes`, `site_*` e do seed), nunca `intermediate` nem `staging`.
- CPF completo nunca vai para o site. Sócios, endereço e contato nunca (só a contagem
  `dim_empresa.socios`).
- Todo arquivo tem `"esquema": 1`; só o `resumo.json` tem `"gerado_em"`.
- Limites: 2.000.000 bytes descomprimido e 500.000 bytes em gzip por arquivo; 200 alertas por
  parlamentar ou empresa (`site_max_alertas`); listas "top" de 20 (`site_top`); bloco de busca
  com mais de 5.000 empresas é subdividido (`site_busca_max`); 500 alertas por página
  (`site_alertas_por_pagina`).
- JSON do site gravado em gzip com `mtime=0` (determinístico) e enviado com
  `Content-Encoding: gzip` e `Cache-Control: public, max-age=600`.
- O `manifesto.json` continua listando só `marts/` e `linhagem/`.
- Mensagens de erro não podem conter o texto onde um CPF foi achado (o log do Actions é público).

## Review Focus

- **`coletor site` falha no pipeline:** os marts devem ser publicados mesmo assim e o `site/` do
  R2 deve ficar com os dados da véspera (nada apagado). Teste:
  `test_sem_site_local_o_site_do_bucket_fica` (tarefa 7); o passo do `pipeline.yml` (tarefa 8)
  roda o `publicar` mesmo com o site falhando.
- **CNPJ alfanumérico (desde 07/2026):** raiz com letras precisa funcionar no bloco
  (`empresa/1AB.json`), nas chaves e nos esquemas. Testes: `site_empresa_em_blocos_com_socios_nas_duas`
  (tarefa 4), `test_esquema_aceita_cnpj_alfanumerico` (tarefa 1) e
  `test_bloco_de_cnpj_alfanumerico` (tarefa 6).
- **Falso positivo de CPF:** valores com 11 dígitos na parte inteira (R$ 10 bi a R$ 100 bi) e MD5
  de `alerta_id` que começa com 11 dígitos não podem bloquear o site (no protótipo, 1.344
  `alerta_id` casavam o padrão). Teste: `test_valor_com_onze_digitos_e_chave_id_nao_sao_cpf`
  (tarefa 6).
- **Lago vazio (CI e primeira execução):** `resumo.json` e `busca/parlamentares.json` precisam
  sair válidos com listas vazias. Verificação: o CI roda `coletor site --target ci` sobre o lago
  vazio (tarefa 8).
- **Objeto enviado antes em multipart:** o ETag não é MD5 e o arquivo precisa ser reenviado (não
  pulado). Teste: `test_etag_que_nao_e_md5_faz_reenviar` (tarefa 7).

## Mapa de arquivos

| Arquivo | Tarefa | Responsabilidade |
|---|---|---|
| `site/esquemas/*.schema.json` (7) | 1 | Contrato de cada tipo de arquivo |
| `site/exemplos/**.json` (10) | 1 | Exemplos fictícios válidos (também fixtures do frontend) |
| `coletor/site.py` | 1, 6 | Tipos, validadores; depois `gerar_site` |
| `tests/test_site.py` | 1, 6 | Contrato; depois `gerar_site` e o comando |
| `dbt/dbt_project.yml` | 2 | Pasta `site`, seeds e variáveis |
| `dbt/seeds/site_alerta_tipos.csv` | 2 | Texto de cada tipo de alerta |
| `dbt/macros/site.sql` | 2 | Macros do formato de alerta, datas e frases |
| `dbt/models/site/site_alertas.sql` (+ `.yml`) | 2 | Alertas no formato comum |
| `dbt/models/site/site_{cota,emendas,contratos,licitacoes}.sql` (+ `site_agregados.yml`) | 3 | Agregados |
| `dbt/models/site/site_arquivos_{parlamentar,empresa}.sql` (+ `site_arquivos_entidades.yml`) | 4 | Arquivos por parlamentar e por bloco de empresas |
| `dbt/models/site/site_arquivos_{busca,alertas,resumo}.sql`, `site_arquivos.sql` (+ `site_arquivos.yml`) | 5 | Busca, alertas paginados, resumo e a união |
| `coletor/cli.py` | 6 | Comando `site` |
| `coletor/publicacao.py`, `tests/test_publicacao.py` | 7 | Envio incremental, gzip, `site/` |
| `.github/workflows/ci.yml`, `pipeline.yml` | 8 | Seeds e `coletor site` no CI; site no passo de publicação |
| `docs/modelos-de-dados.md`, `AGENTS.md`, `docs/roteiro.md`, `README.md` | 8 | Documentação |

## Como rodar o dbt sobre o lago vazio (vale para as tarefas 2 a 5)

Em PowerShell, na raiz do repositório (é o que o CI faz, mais o `seed`):

```powershell
$env:ELEITORADO_LAGO = "dbt/tests/lago_vazio"; $env:ELEITORADO_PUBLICO = "$env:TEMP\publico-ci"
uv run python scripts/lago_vazio.py
New-Item -ItemType Directory -Force "$env:ELEITORADO_PUBLICO\marts" | Out-Null
uv run dbt seed --project-dir dbt --profiles-dir dbt --target ci
uv run dbt run --project-dir dbt --profiles-dir dbt --target ci
uv run dbt test --project-dir dbt --profiles-dir dbt --target ci
```

Para um teste unitário só: `uv run dbt test --project-dir dbt --profiles-dir dbt --target ci
--select "test_name:<nome>"` (depois de um `dbt run` completo, para os marts existirem).

---

### Task 1: Contrato do site (JSON Schemas, exemplos e validadores)

**Files:**
- Create: `site/esquemas/comum.schema.json`, `resumo.schema.json`,
  `busca-parlamentares.schema.json`, `busca-empresas.schema.json`, `parlamentar.schema.json`,
  `empresa.schema.json`, `alertas.schema.json`
- Create: `site/exemplos/resumo.json`, `busca/parlamentares.json`, `busca/empresas/emp.json`,
  `busca/empresas/exe.json`, `busca/empresas/con.json`, `busca/empresas/cons.json`,
  `parlamentar/camara-900001.json`, `parlamentar/senado-900002.json`, `empresa/112.json`,
  `alertas/cota_fornecedor_sancionado/1.json`
- Create: `coletor/site.py` (parcial; a tarefa 6 completa)
- Create: `tests/test_site.py` (parcial; a tarefa 6 acrescenta)
- Modify: `pyproject.toml`, `uv.lock` (dependência `jsonschema`)

**Interfaces:**
- Produces: `coletor.site.TIPOS: tuple[str, ...]`, `coletor.site.ErroSite(Exception)`,
  `coletor.site.tipo_do_caminho(caminho: str) -> str`,
  `coletor.site.carregar_validadores(pasta: Path) -> dict[str, Draft202012Validator]`. Os
  esquemas e exemplos são o contrato do plano 11 (frontend).

- [ ] **Step 1: Adicione a dependência**

Run: `uv add jsonschema`
Expected: `pyproject.toml` ganha `jsonschema>=…` em `dependencies` e o `uv.lock` é atualizado.

- [ ] **Step 2: Crie os JSON Schemas**

`site/esquemas/comum.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://eleitorado.pages.dev/esquemas/comum.schema.json",
  "title": "Definições comuns aos arquivos do site",
  "$defs": {
    "esquema": { "const": 1 },
    "data": { "type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$" },
    "data_ou_nulo": { "anyOf": [{ "$ref": "#/$defs/data" }, { "type": "null" }] },
    "instante": {
      "type": "string",
      "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
    },
    "instante_ou_nulo": { "anyOf": [{ "$ref": "#/$defs/instante" }, { "type": "null" }] },
    "valor": { "type": "number" },
    "valor_ou_nulo": { "type": ["number", "null"] },
    "inteiro": { "type": "integer", "minimum": 0 },
    "inteiro_ou_nulo": { "type": ["integer", "null"] },
    "texto": { "type": "string" },
    "texto_ou_nulo": { "type": ["string", "null"] },
    "raiz": { "type": "string", "pattern": "^[0-9A-Z]{8}$" },
    "raiz_ou_nulo": { "anyOf": [{ "$ref": "#/$defs/raiz" }, { "type": "null" }] },
    "parlamentar_id": { "type": "string", "pattern": "^(camara|senado):[0-9A-Za-z]+$" },
    "parlamentar_id_ou_nulo": {
      "anyOf": [{ "$ref": "#/$defs/parlamentar_id" }, { "type": "null" }]
    },
    "casa": { "enum": ["camara", "senado"] },
    "alerta": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "alerta_id", "tipo", "data", "valor", "parlamentar_id", "parlamentar_nome", "cnpj_raiz",
        "empresa_nome", "cnpj_raiz_2", "empresa_nome_2", "descricao", "correspondencia", "regra"
      ],
      "properties": {
        "alerta_id": { "$ref": "#/$defs/texto" },
        "tipo": { "type": "string", "pattern": "^[a-z_]+$" },
        "data": { "$ref": "#/$defs/data_ou_nulo" },
        "valor": { "$ref": "#/$defs/valor_ou_nulo" },
        "parlamentar_id": { "$ref": "#/$defs/parlamentar_id_ou_nulo" },
        "parlamentar_nome": { "$ref": "#/$defs/texto_ou_nulo" },
        "cnpj_raiz": { "$ref": "#/$defs/raiz_ou_nulo" },
        "empresa_nome": { "$ref": "#/$defs/texto_ou_nulo" },
        "cnpj_raiz_2": { "$ref": "#/$defs/raiz_ou_nulo" },
        "empresa_nome_2": { "$ref": "#/$defs/texto_ou_nulo" },
        "descricao": { "$ref": "#/$defs/texto" },
        "correspondencia": { "enum": ["forte", "fraca"] },
        "regra": { "$ref": "#/$defs/texto" }
      }
    },
    "alertas": {
      "type": "object",
      "additionalProperties": false,
      "required": ["total", "itens"],
      "properties": {
        "total": { "$ref": "#/$defs/inteiro" },
        "itens": { "type": "array", "items": { "$ref": "#/$defs/alerta" } }
      }
    },
    "parlamentar_resumo": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "nome", "casa", "uf", "partido", "foto", "legislaturas"],
      "properties": {
        "id": { "$ref": "#/$defs/parlamentar_id" },
        "nome": { "$ref": "#/$defs/texto_ou_nulo" },
        "casa": { "$ref": "#/$defs/casa" },
        "uf": { "$ref": "#/$defs/texto_ou_nulo" },
        "partido": { "$ref": "#/$defs/texto_ou_nulo" },
        "foto": { "$ref": "#/$defs/texto_ou_nulo" },
        "legislaturas": { "type": "array", "items": { "type": "integer" } }
      }
    }
  }
}
```

`site/esquemas/resumo.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://eleitorado.pages.dev/esquemas/resumo.schema.json",
  "title": "resumo.json: números da capa, tipos de alerta e situação das fontes",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "esquema", "gerado_em", "dados_ate", "totais", "alerta_tipos", "alertas_recentes", "fontes",
    "fontes_reduzidas"
  ],
  "properties": {
    "esquema": { "$ref": "comum.schema.json#/$defs/esquema" },
    "gerado_em": { "$ref": "comum.schema.json#/$defs/instante" },
    "dados_ate": {
      "type": "object",
      "additionalProperties": false,
      "required": ["cota", "emendas", "contratos", "receita"],
      "properties": {
        "cota": { "$ref": "comum.schema.json#/$defs/data_ou_nulo" },
        "emendas": { "$ref": "comum.schema.json#/$defs/data_ou_nulo" },
        "contratos": { "$ref": "comum.schema.json#/$defs/data_ou_nulo" },
        "receita": { "type": ["string", "null"], "pattern": "^[0-9]{4}-[0-9]{2}$" }
      }
    },
    "totais": {
      "type": "object",
      "additionalProperties": false,
      "required": ["cota", "emendas_pago", "contratos", "parlamentares", "empresas"],
      "properties": {
        "cota": { "$ref": "comum.schema.json#/$defs/valor" },
        "emendas_pago": { "$ref": "comum.schema.json#/$defs/valor" },
        "contratos": { "$ref": "comum.schema.json#/$defs/valor" },
        "parlamentares": { "$ref": "comum.schema.json#/$defs/inteiro" },
        "empresas": { "$ref": "comum.schema.json#/$defs/inteiro" }
      }
    },
    "alerta_tipos": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["tipo", "titulo", "explicacao", "cautela", "ordem", "quantidade"],
        "properties": {
          "tipo": { "type": "string", "pattern": "^[a-z_]+$" },
          "titulo": { "$ref": "comum.schema.json#/$defs/texto" },
          "explicacao": { "$ref": "comum.schema.json#/$defs/texto" },
          "cautela": { "$ref": "comum.schema.json#/$defs/texto" },
          "ordem": { "type": "integer" },
          "quantidade": { "$ref": "comum.schema.json#/$defs/inteiro" }
        }
      }
    },
    "alertas_recentes": {
      "type": "array",
      "maxItems": 20,
      "items": { "$ref": "comum.schema.json#/$defs/alerta" }
    },
    "fontes": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "recurso_id", "cadencia", "ultimo_sucesso", "status", "atraso_horas", "situacao"
        ],
        "properties": {
          "recurso_id": { "$ref": "comum.schema.json#/$defs/texto" },
          "cadencia": { "$ref": "comum.schema.json#/$defs/texto_ou_nulo" },
          "ultimo_sucesso": { "$ref": "comum.schema.json#/$defs/instante_ou_nulo" },
          "status": { "$ref": "comum.schema.json#/$defs/texto_ou_nulo" },
          "atraso_horas": { "$ref": "comum.schema.json#/$defs/inteiro_ou_nulo" },
          "situacao": { "enum": ["ok", "aviso", "erro"] }
        }
      }
    },
    "fontes_reduzidas": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "recurso_id", "competencia", "coletada_em", "linhas_antes", "linhas_depois",
          "variacao_pct"
        ],
        "properties": {
          "recurso_id": { "$ref": "comum.schema.json#/$defs/texto" },
          "competencia": { "$ref": "comum.schema.json#/$defs/texto_ou_nulo" },
          "coletada_em": { "$ref": "comum.schema.json#/$defs/instante_ou_nulo" },
          "linhas_antes": { "$ref": "comum.schema.json#/$defs/inteiro_ou_nulo" },
          "linhas_depois": { "$ref": "comum.schema.json#/$defs/inteiro_ou_nulo" },
          "variacao_pct": { "$ref": "comum.schema.json#/$defs/valor_ou_nulo" }
        }
      }
    }
  }
}
```

`site/esquemas/busca-parlamentares.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://eleitorado.pages.dev/esquemas/busca-parlamentares.schema.json",
  "title": "busca/parlamentares.json: todos os parlamentares, para a busca",
  "type": "object",
  "additionalProperties": false,
  "required": ["esquema", "parlamentares"],
  "properties": {
    "esquema": { "$ref": "comum.schema.json#/$defs/esquema" },
    "parlamentares": {
      "type": "array",
      "items": { "$ref": "comum.schema.json#/$defs/parlamentar_resumo" }
    }
  }
}
```

`site/esquemas/busca-empresas.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://eleitorado.pages.dev/esquemas/busca-empresas.schema.json",
  "title": "busca/empresas/<prefixo>.json: empresas com uma palavra da razão social começando pelo prefixo",
  "type": "object",
  "additionalProperties": false,
  "required": ["esquema", "prefixo", "subdividido", "empresas"],
  "properties": {
    "esquema": { "$ref": "comum.schema.json#/$defs/esquema" },
    "prefixo": { "type": "string", "pattern": "^[a-z0-9]{3,4}$" },
    "subdividido": { "type": "boolean" },
    "empresas": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["raiz", "nome", "uf", "situacao"],
        "properties": {
          "raiz": { "$ref": "comum.schema.json#/$defs/raiz" },
          "nome": { "$ref": "comum.schema.json#/$defs/texto_ou_nulo" },
          "uf": { "$ref": "comum.schema.json#/$defs/texto_ou_nulo" },
          "situacao": { "$ref": "comum.schema.json#/$defs/texto_ou_nulo" }
        }
      }
    }
  }
}
```

`site/esquemas/parlamentar.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://eleitorado.pages.dev/esquemas/parlamentar.schema.json",
  "title": "parlamentar/<casa>-<id>.json: cota, emendas e alertas de um parlamentar",
  "type": "object",
  "additionalProperties": false,
  "required": ["esquema", "parlamentar", "cota", "emendas", "alertas"],
  "properties": {
    "esquema": { "$ref": "comum.schema.json#/$defs/esquema" },
    "parlamentar": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "nome", "casa", "uf", "partido", "foto", "legislaturas", "url_oficial"],
      "properties": {
        "id": { "$ref": "comum.schema.json#/$defs/parlamentar_id" },
        "nome": { "$ref": "comum.schema.json#/$defs/texto_ou_nulo" },
        "casa": { "$ref": "comum.schema.json#/$defs/casa" },
        "uf": { "$ref": "comum.schema.json#/$defs/texto_ou_nulo" },
        "partido": { "$ref": "comum.schema.json#/$defs/texto_ou_nulo" },
        "foto": { "$ref": "comum.schema.json#/$defs/texto_ou_nulo" },
        "legislaturas": { "type": "array", "items": { "type": "integer" } },
        "url_oficial": { "type": "string", "pattern": "^https://" }
      }
    },
    "cota": {
      "type": "object",
      "additionalProperties": false,
      "required": ["total", "por_ano", "por_categoria", "fornecedores"],
      "properties": {
        "total": { "$ref": "comum.schema.json#/$defs/valor" },
        "por_ano": {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["ano", "valor"],
            "properties": {
              "ano": { "type": "integer" },
              "valor": { "$ref": "comum.schema.json#/$defs/valor" }
            }
          }
        },
        "por_categoria": {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["categoria", "valor"],
            "properties": {
              "categoria": { "$ref": "comum.schema.json#/$defs/texto_ou_nulo" },
              "valor": { "$ref": "comum.schema.json#/$defs/valor" }
            }
          }
        },
        "fornecedores": {
          "type": "array",
          "maxItems": 20,
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["nome", "documento", "cnpj_raiz", "valor", "despesas"],
            "properties": {
              "nome": { "$ref": "comum.schema.json#/$defs/texto_ou_nulo" },
              "documento": { "$ref": "comum.schema.json#/$defs/texto_ou_nulo" },
              "cnpj_raiz": { "$ref": "comum.schema.json#/$defs/raiz_ou_nulo" },
              "valor": { "$ref": "comum.schema.json#/$defs/valor" },
              "despesas": { "$ref": "comum.schema.json#/$defs/inteiro" }
            }
          }
        }
      }
    },
    "emendas": {
      "type": "object",
      "additionalProperties": false,
      "required": ["total_pago", "por_ano", "favorecidos"],
      "properties": {
        "total_pago": { "$ref": "comum.schema.json#/$defs/valor" },
        "por_ano": {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["ano", "pago"],
            "properties": {
              "ano": { "type": "integer" },
              "pago": { "$ref": "comum.schema.json#/$defs/valor" }
            }
          }
        },
        "favorecidos": {
          "type": "array",
          "maxItems": 20,
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["nome", "documento", "cnpj_raiz", "pago"],
            "properties": {
              "nome": { "$ref": "comum.schema.json#/$defs/texto_ou_nulo" },
              "documento": { "$ref": "comum.schema.json#/$defs/texto_ou_nulo" },
              "cnpj_raiz": { "$ref": "comum.schema.json#/$defs/raiz_ou_nulo" },
              "pago": { "$ref": "comum.schema.json#/$defs/valor" }
            }
          }
        }
      }
    },
    "alertas": { "$ref": "comum.schema.json#/$defs/alertas" }
  }
}
```

`site/esquemas/empresa.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://eleitorado.pages.dev/esquemas/empresa.schema.json",
  "title": "empresa/<bloco>.json: empresas cuja raiz do CNPJ começa pelo bloco",
  "type": "object",
  "additionalProperties": false,
  "required": ["esquema", "bloco", "empresas"],
  "properties": {
    "esquema": { "$ref": "comum.schema.json#/$defs/esquema" },
    "bloco": { "type": "string", "pattern": "^[0-9A-Z]{3}$" },
    "empresas": {
      "type": "object",
      "propertyNames": { "pattern": "^[0-9A-Z]{8}$" },
      "additionalProperties": { "$ref": "#/$defs/empresa" }
    }
  },
  "$defs": {
    "empresa": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "cadastro", "cota", "emendas", "contratos", "licitacoes", "sancoes", "alertas"
      ],
      "properties": {
        "cadastro": {
          "type": "object",
          "additionalProperties": false,
          "required": [
            "razao_social", "natureza_juridica", "porte", "capital_social", "abertura",
            "situacao", "data_situacao", "motivo_situacao", "atividade", "municipio", "uf",
            "optante_simples", "optante_mei", "estabelecimentos", "socios", "matriz_cnpj",
            "url_portal", "competencia_receita"
          ],
          "properties": {
            "razao_social": { "$ref": "comum.schema.json#/$defs/texto_ou_nulo" },
            "natureza_juridica": { "$ref": "comum.schema.json#/$defs/texto_ou_nulo" },
            "porte": { "$ref": "comum.schema.json#/$defs/texto_ou_nulo" },
            "capital_social": { "$ref": "comum.schema.json#/$defs/valor_ou_nulo" },
            "abertura": { "$ref": "comum.schema.json#/$defs/data_ou_nulo" },
            "situacao": { "$ref": "comum.schema.json#/$defs/texto_ou_nulo" },
            "data_situacao": { "$ref": "comum.schema.json#/$defs/data_ou_nulo" },
            "motivo_situacao": { "$ref": "comum.schema.json#/$defs/texto_ou_nulo" },
            "atividade": { "$ref": "comum.schema.json#/$defs/texto_ou_nulo" },
            "municipio": { "$ref": "comum.schema.json#/$defs/texto_ou_nulo" },
            "uf": { "$ref": "comum.schema.json#/$defs/texto_ou_nulo" },
            "optante_simples": { "type": ["boolean", "null"] },
            "optante_mei": { "type": ["boolean", "null"] },
            "estabelecimentos": { "$ref": "comum.schema.json#/$defs/inteiro_ou_nulo" },
            "socios": { "$ref": "comum.schema.json#/$defs/inteiro_ou_nulo" },
            "matriz_cnpj": { "$ref": "comum.schema.json#/$defs/texto_ou_nulo" },
            "url_portal": { "type": ["string", "null"], "pattern": "^https://" },
            "competencia_receita": { "$ref": "comum.schema.json#/$defs/texto_ou_nulo" }
          }
        },
        "cota": {
          "type": "object",
          "additionalProperties": false,
          "required": ["total", "parlamentares"],
          "properties": {
            "total": { "$ref": "comum.schema.json#/$defs/valor" },
            "parlamentares": {
              "type": "array",
              "maxItems": 20,
              "items": {
                "type": "object",
                "additionalProperties": false,
                "required": ["parlamentar_id", "nome", "valor"],
                "properties": {
                  "parlamentar_id": { "$ref": "comum.schema.json#/$defs/parlamentar_id" },
                  "nome": { "$ref": "comum.schema.json#/$defs/texto_ou_nulo" },
                  "valor": { "$ref": "comum.schema.json#/$defs/valor" }
                }
              }
            }
          }
        },
        "emendas": {
          "type": "object",
          "additionalProperties": false,
          "required": ["total_pago", "autores"],
          "properties": {
            "total_pago": { "$ref": "comum.schema.json#/$defs/valor" },
            "autores": {
              "type": "array",
              "maxItems": 20,
              "items": {
                "type": "object",
                "additionalProperties": false,
                "required": ["autor", "parlamentar_id", "pago"],
                "properties": {
                  "autor": { "$ref": "comum.schema.json#/$defs/texto_ou_nulo" },
                  "parlamentar_id": { "$ref": "comum.schema.json#/$defs/parlamentar_id_ou_nulo" },
                  "pago": { "$ref": "comum.schema.json#/$defs/valor" }
                }
              }
            }
          }
        },
        "contratos": {
          "type": "object",
          "additionalProperties": false,
          "required": ["total", "quantidade", "orgaos"],
          "properties": {
            "total": { "$ref": "comum.schema.json#/$defs/valor" },
            "quantidade": { "$ref": "comum.schema.json#/$defs/inteiro" },
            "orgaos": {
              "type": "array",
              "maxItems": 20,
              "items": {
                "type": "object",
                "additionalProperties": false,
                "required": ["orgao", "valor", "contratos"],
                "properties": {
                  "orgao": { "$ref": "comum.schema.json#/$defs/texto_ou_nulo" },
                  "valor": { "$ref": "comum.schema.json#/$defs/valor" },
                  "contratos": { "$ref": "comum.schema.json#/$defs/inteiro" }
                }
              }
            }
          }
        },
        "licitacoes": {
          "type": "object",
          "additionalProperties": false,
          "required": ["vencidas"],
          "properties": { "vencidas": { "$ref": "comum.schema.json#/$defs/inteiro" } }
        },
        "sancoes": {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["sancao_id", "cadastro", "categoria", "orgao", "inicio", "fim", "vigente"],
            "properties": {
              "sancao_id": { "$ref": "comum.schema.json#/$defs/texto" },
              "cadastro": { "$ref": "comum.schema.json#/$defs/texto_ou_nulo" },
              "categoria": { "$ref": "comum.schema.json#/$defs/texto_ou_nulo" },
              "orgao": { "$ref": "comum.schema.json#/$defs/texto_ou_nulo" },
              "inicio": { "$ref": "comum.schema.json#/$defs/data_ou_nulo" },
              "fim": { "$ref": "comum.schema.json#/$defs/data_ou_nulo" },
              "vigente": { "type": "boolean" }
            }
          }
        },
        "alertas": { "$ref": "comum.schema.json#/$defs/alertas" }
      }
    }
  }
}
```

`site/esquemas/alertas.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://eleitorado.pages.dev/esquemas/alertas.schema.json",
  "title": "alertas/<tipo>/<pagina>.json: uma página dos alertas de um tipo",
  "type": "object",
  "additionalProperties": false,
  "required": ["esquema", "tipo", "pagina", "paginas", "total", "alertas"],
  "properties": {
    "esquema": { "$ref": "comum.schema.json#/$defs/esquema" },
    "tipo": { "type": "string", "pattern": "^[a-z_]+$" },
    "pagina": { "type": "integer", "minimum": 1 },
    "paginas": { "type": "integer", "minimum": 1 },
    "total": { "$ref": "comum.schema.json#/$defs/inteiro" },
    "alertas": { "type": "array", "items": { "$ref": "comum.schema.json#/$defs/alerta" } }
  }
}
```

- [ ] **Step 3: Crie os exemplos (dados fictícios)**

Nomes e ids são inventados de propósito (o repositório é público): não use parlamentares nem
empresas reais nos exemplos.

`site/exemplos/resumo.json`:

```json
{
  "esquema": 1,
  "gerado_em": "2026-10-07T11:02:13Z",
  "dados_ate": {
    "cota": "2026-09-01",
    "emendas": "2026-10-03",
    "contratos": "2026-10-05",
    "receita": "2026-09"
  },
  "totais": {
    "cota": 1500.0,
    "emendas_pago": 250000.0,
    "contratos": 350000.0,
    "parlamentares": 2,
    "empresas": 2
  },
  "alerta_tipos": [
    {
      "tipo": "cota_fornecedor_sancionado",
      "titulo": "Cota paga a fornecedor sancionado",
      "explicacao": "O parlamentar foi reembolsado pela cota por uma despesa com fornecedor que, na data da nota, estava no cadastro de punidos da CGU (CEIS ou CNEP).",
      "cautela": "A cota reembolsa gastos do parlamentar (não é contratação pública), e a sanção pode valer só para o órgão que a aplicou.",
      "ordem": 1,
      "quantidade": 1
    },
    {
      "tipo": "cota_documento_invalido",
      "titulo": "Cota com CPF ou CNPJ inválido",
      "explicacao": "A despesa de cota traz um CPF ou CNPJ de fornecedor com tamanho ou dígito verificador errado.",
      "cautela": "Pode ser só um erro de digitação na prestação de contas.",
      "ordem": 2,
      "quantidade": 0
    },
    {
      "tipo": "emenda_favorecido_sancionado",
      "titulo": "Emenda paga a favorecido sancionado",
      "explicacao": "Um pagamento de emenda parlamentar foi feito a empresa que, na data do pagamento, estava no CEIS ou no CNEP.",
      "cautela": "A sanção pode valer só para o órgão que a aplicou; o parlamentar indica a emenda, mas quem paga é o órgão executor.",
      "ordem": 3,
      "quantidade": 0
    },
    {
      "tipo": "contrato_fornecedor_sancionado",
      "titulo": "Contrato com fornecedor sancionado",
      "explicacao": "Um contrato federal foi assinado com empresa que, na data da assinatura, estava no CEIS ou no CNEP.",
      "cautela": "A sanção pode valer só para o órgão que a aplicou.",
      "ordem": 4,
      "quantidade": 0
    },
    {
      "tipo": "licitacao_vencedor_sancionado",
      "titulo": "Licitação vencida por sancionado",
      "explicacao": "O vencedor de uma licitação federal estava no CEIS ou no CNEP na data da licitação.",
      "cautela": "A sanção pode valer só para o órgão que a aplicou.",
      "ordem": 5,
      "quantidade": 0
    },
    {
      "tipo": "pagamento_empresa_irregular",
      "titulo": "Pagamento a empresa irregular na Receita",
      "explicacao": "Despesa de cota, pagamento de emenda ou contrato com empresa que já estava baixada, inapta, suspensa ou nula na Receita na data do fato.",
      "cautela": "A Receita informa só a situação atual e desde quando ela vale; reativações anteriores não aparecem.",
      "ordem": 6,
      "quantidade": 0
    },
    {
      "tipo": "empresa_recem_aberta",
      "titulo": "Empresa recém-aberta",
      "explicacao": "Contrato ou pagamento de emenda de pelo menos R$ 50 mil, ou despesa de cota de pelo menos R$ 10 mil, com empresa aberta até 180 dias antes.",
      "cautela": "Empresa nova não é irregular: o alerta só aponta onde vale olhar com mais atenção.",
      "ordem": 7,
      "quantidade": 0
    },
    {
      "tipo": "licitacao_socios_em_comum",
      "titulo": "Concorrentes com sócios em comum",
      "explicacao": "Duas empresas que disputaram a mesma licitação tinham pelo menos um sócio em comum desde antes da licitação.",
      "cautela": "Os sócios são os da base mais recente da Receita: quem saiu antes não aparece, e ter sócio em comum não prova combinação.",
      "ordem": 8,
      "quantidade": 1
    },
    {
      "tipo": "parlamentar_socio_fornecedor",
      "titulo": "Parlamentar sócio de empresa",
      "explicacao": "O parlamentar aparece como sócio de uma empresa que está nos dados públicos (fornecedor, favorecido ou contratada).",
      "cautela": "Deputados são identificados pelo nome e por parte do CPF; senadores, só pelo nome, e podem ser homônimos.",
      "ordem": 9,
      "quantidade": 1
    }
  ],
  "alertas_recentes": [
    {
      "alerta_id": "7c1e0d2a9f4b4e6a8d3c2b1a0f9e8d7c",
      "tipo": "cota_fornecedor_sancionado",
      "data": "2026-08-14",
      "valor": 1200.0,
      "parlamentar_id": "camara:900001",
      "parlamentar_nome": "ANA EXEMPLO",
      "cnpj_raiz": "11222333",
      "empresa_nome": "EMPRESA EXEMPLO LTDA",
      "cnpj_raiz_2": null,
      "empresa_nome_2": null,
      "descricao": "Despesa de cota com fornecedor sancionado no CEIS por MINISTERIO EXEMPLO desde 01/03/2025",
      "correspondencia": "forte",
      "regra": "Despesa de cota com fornecedor que tinha sanção vigente (CEIS ou CNEP) na data de emissão do documento"
    },
    {
      "alerta_id": "c3a7b2d4e6f8091a2b3c4d5e6f708192",
      "tipo": "licitacao_socios_em_comum",
      "data": "2023-05-05",
      "valor": null,
      "parlamentar_id": null,
      "parlamentar_nome": null,
      "cnpj_raiz": "11222333",
      "empresa_nome": "EMPRESA EXEMPLO LTDA",
      "cnpj_raiz_2": "44555666",
      "empresa_nome_2": "EMPREITEIRA MODELO SA",
      "descricao": "Participantes da mesma licitação de MINISTERIO EXEMPLO com 2 sócio(s) em comum",
      "correspondencia": "forte",
      "regra": "Dois participantes da mesma licitação com sócio em comum desde antes da licitação"
    }
  ],
  "fontes": [
    {
      "recurso_id": "camara.cota",
      "cadencia": "diaria",
      "ultimo_sucesso": "2026-10-07T10:40:00Z",
      "status": "carregada",
      "atraso_horas": 0,
      "situacao": "ok"
    },
    {
      "recurso_id": "rfb.empresas",
      "cadencia": "mensal",
      "ultimo_sucesso": null,
      "status": null,
      "atraso_horas": null,
      "situacao": "erro"
    }
  ],
  "fontes_reduzidas": [
    {
      "recurso_id": "camara.cota",
      "competencia": "2015",
      "coletada_em": "2026-10-05T11:00:00Z",
      "linhas_antes": 1000,
      "linhas_depois": 850,
      "variacao_pct": -15.0
    }
  ]
}
```

`site/exemplos/busca/parlamentares.json`:

```json
{
  "esquema": 1,
  "parlamentares": [
    {
      "id": "camara:900001",
      "nome": "ANA EXEMPLO",
      "casa": "camara",
      "uf": "DF",
      "partido": "PEX",
      "foto": null,
      "legislaturas": [
        56,
        57
      ]
    },
    {
      "id": "senado:900002",
      "nome": "JOAO MODELO",
      "casa": "senado",
      "uf": "SP",
      "partido": "PMO",
      "foto": null,
      "legislaturas": [
        57
      ]
    }
  ]
}
```

`site/exemplos/busca/empresas/emp.json`:

```json
{
  "esquema": 1,
  "prefixo": "emp",
  "subdividido": false,
  "empresas": [
    {
      "raiz": "44555666",
      "nome": "EMPREITEIRA MODELO SA",
      "uf": "SP",
      "situacao": "ATIVA"
    },
    {
      "raiz": "11222333",
      "nome": "EMPRESA EXEMPLO LTDA",
      "uf": "DF",
      "situacao": "ATIVA"
    }
  ]
}
```

`site/exemplos/busca/empresas/exe.json`:

```json
{
  "esquema": 1,
  "prefixo": "exe",
  "subdividido": false,
  "empresas": [
    {
      "raiz": "11222333",
      "nome": "EMPRESA EXEMPLO LTDA",
      "uf": "DF",
      "situacao": "ATIVA"
    }
  ]
}
```

`site/exemplos/busca/empresas/con.json` (bloco subdividido: só a empresa de palavra com
exatamente 3 letras):

```json
{
  "esquema": 1,
  "prefixo": "con",
  "subdividido": true,
  "empresas": [
    {
      "raiz": "77888999",
      "nome": "CON ENGENHARIA SA",
      "uf": "RJ",
      "situacao": "BAIXADA"
    }
  ]
}
```

`site/exemplos/busca/empresas/cons.json`:

```json
{
  "esquema": 1,
  "prefixo": "cons",
  "subdividido": false,
  "empresas": [
    {
      "raiz": "55666777",
      "nome": "CONSTRUTORA EXEMPLO LTDA",
      "uf": "MG",
      "situacao": "INAPTA"
    }
  ]
}
```

`site/exemplos/parlamentar/camara-900001.json`:

```json
{
  "esquema": 1,
  "parlamentar": {
    "id": "camara:900001",
    "nome": "ANA EXEMPLO",
    "casa": "camara",
    "uf": "DF",
    "partido": "PEX",
    "foto": null,
    "legislaturas": [
      56,
      57
    ],
    "url_oficial": "https://www.camara.leg.br/deputados/900001"
  },
  "cota": {
    "total": 1500.0,
    "por_ano": [
      {
        "ano": 2025,
        "valor": 300.0
      },
      {
        "ano": 2026,
        "valor": 1200.0
      }
    ],
    "por_categoria": [
      {
        "categoria": "DIVULGAÇÃO DA ATIVIDADE PARLAMENTAR.",
        "valor": 1200.0
      },
      {
        "categoria": "COMBUSTÍVEIS E LUBRIFICANTES.",
        "valor": 300.0
      }
    ],
    "fornecedores": [
      {
        "nome": "EMPRESA EXEMPLO LTDA",
        "documento": "11222333000181",
        "cnpj_raiz": "11222333",
        "valor": 1200.0,
        "despesas": 1
      },
      {
        "nome": "MARIA EXEMPLO",
        "documento": "***.456.789-**",
        "cnpj_raiz": null,
        "valor": 300.0,
        "despesas": 2
      }
    ]
  },
  "emendas": {
    "total_pago": 250000.0,
    "por_ano": [
      {
        "ano": 2025,
        "pago": 250000.0
      }
    ],
    "favorecidos": [
      {
        "nome": "MUNICIPIO DE EXEMPLO",
        "documento": "99888777000166",
        "cnpj_raiz": "99888777",
        "pago": 250000.0
      }
    ]
  },
  "alertas": {
    "total": 1,
    "itens": [
      {
        "alerta_id": "7c1e0d2a9f4b4e6a8d3c2b1a0f9e8d7c",
        "tipo": "cota_fornecedor_sancionado",
        "data": "2026-08-14",
        "valor": 1200.0,
        "parlamentar_id": "camara:900001",
        "parlamentar_nome": "ANA EXEMPLO",
        "cnpj_raiz": "11222333",
        "empresa_nome": "EMPRESA EXEMPLO LTDA",
        "cnpj_raiz_2": null,
        "empresa_nome_2": null,
        "descricao": "Despesa de cota com fornecedor sancionado no CEIS por MINISTERIO EXEMPLO desde 01/03/2025",
        "correspondencia": "forte",
        "regra": "Despesa de cota com fornecedor que tinha sanção vigente (CEIS ou CNEP) na data de emissão do documento"
      }
    ]
  }
}
```

`site/exemplos/parlamentar/senado-900002.json`:

```json
{
  "esquema": 1,
  "parlamentar": {
    "id": "senado:900002",
    "nome": "JOAO MODELO",
    "casa": "senado",
    "uf": "SP",
    "partido": "PMO",
    "foto": null,
    "legislaturas": [
      57
    ],
    "url_oficial": "https://www25.senado.leg.br/web/senadores/senador/-/perfil/900002"
  },
  "cota": {
    "total": 0,
    "por_ano": [],
    "por_categoria": [],
    "fornecedores": []
  },
  "emendas": {
    "total_pago": 0,
    "por_ano": [],
    "favorecidos": []
  },
  "alertas": {
    "total": 1,
    "itens": [
      {
        "alerta_id": "b2f6a1c3d4e5f60718293a4b5c6d7e8f",
        "tipo": "parlamentar_socio_fornecedor",
        "data": "2019-05-20",
        "valor": null,
        "parlamentar_id": "senado:900002",
        "parlamentar_nome": "JOAO MODELO",
        "cnpj_raiz": "11222333",
        "empresa_nome": "EMPRESA EXEMPLO LTDA",
        "cnpj_raiz_2": null,
        "empresa_nome_2": null,
        "descricao": "Parlamentar sócio da empresa desde 20/05/2019",
        "correspondencia": "fraca",
        "regra": "Parlamentar sócio (pessoa física) de empresa que aparece nos dados; senador só pelo nome"
      }
    ]
  }
}
```

`site/exemplos/empresa/112.json`:

```json
{
  "esquema": 1,
  "bloco": "112",
  "empresas": {
    "11222333": {
      "cadastro": {
        "razao_social": "EMPRESA EXEMPLO LTDA",
        "natureza_juridica": "Sociedade Empresária Limitada",
        "porte": "MICRO EMPRESA",
        "capital_social": 50000.0,
        "abertura": "2018-04-02",
        "situacao": "ATIVA",
        "data_situacao": "2018-04-02",
        "motivo_situacao": "SEM MOTIVO",
        "atividade": "Serviços de publicidade",
        "municipio": "BRASILIA",
        "uf": "DF",
        "optante_simples": true,
        "optante_mei": false,
        "estabelecimentos": 1,
        "socios": 2,
        "matriz_cnpj": "11222333000181",
        "url_portal": "https://portaldatransparencia.gov.br/busca?termo=11222333000181",
        "competencia_receita": "2026-09"
      },
      "cota": {
        "total": 1200.0,
        "parlamentares": [
          {
            "parlamentar_id": "camara:900001",
            "nome": "ANA EXEMPLO",
            "valor": 1200.0
          }
        ]
      },
      "emendas": {
        "total_pago": 0,
        "autores": []
      },
      "contratos": {
        "total": 350000.0,
        "quantidade": 2,
        "orgaos": [
          {
            "orgao": "MINISTERIO EXEMPLO",
            "valor": 350000.0,
            "contratos": 2
          }
        ]
      },
      "licitacoes": {
        "vencidas": 1
      },
      "sancoes": [
        {
          "sancao_id": "CEIS:123456",
          "cadastro": "CEIS",
          "categoria": "Impedimento/proibição de contratar com prazo determinado",
          "orgao": "MINISTERIO EXEMPLO",
          "inicio": "2025-03-01",
          "fim": "2027-03-01",
          "vigente": true
        }
      ],
      "alertas": {
        "total": 3,
        "itens": [
          {
            "alerta_id": "7c1e0d2a9f4b4e6a8d3c2b1a0f9e8d7c",
            "tipo": "cota_fornecedor_sancionado",
            "data": "2026-08-14",
            "valor": 1200.0,
            "parlamentar_id": "camara:900001",
            "parlamentar_nome": "ANA EXEMPLO",
            "cnpj_raiz": "11222333",
            "empresa_nome": "EMPRESA EXEMPLO LTDA",
            "cnpj_raiz_2": null,
            "empresa_nome_2": null,
            "descricao": "Despesa de cota com fornecedor sancionado no CEIS por MINISTERIO EXEMPLO desde 01/03/2025",
            "correspondencia": "forte",
            "regra": "Despesa de cota com fornecedor que tinha sanção vigente (CEIS ou CNEP) na data de emissão do documento"
          },
          {
            "alerta_id": "c3a7b2d4e6f8091a2b3c4d5e6f708192",
            "tipo": "licitacao_socios_em_comum",
            "data": "2023-05-05",
            "valor": null,
            "parlamentar_id": null,
            "parlamentar_nome": null,
            "cnpj_raiz": "11222333",
            "empresa_nome": "EMPRESA EXEMPLO LTDA",
            "cnpj_raiz_2": "44555666",
            "empresa_nome_2": "EMPREITEIRA MODELO SA",
            "descricao": "Participantes da mesma licitação de MINISTERIO EXEMPLO com 2 sócio(s) em comum",
            "correspondencia": "forte",
            "regra": "Dois participantes da mesma licitação com sócio em comum desde antes da licitação"
          },
          {
            "alerta_id": "b2f6a1c3d4e5f60718293a4b5c6d7e8f",
            "tipo": "parlamentar_socio_fornecedor",
            "data": "2019-05-20",
            "valor": null,
            "parlamentar_id": "senado:900002",
            "parlamentar_nome": "JOAO MODELO",
            "cnpj_raiz": "11222333",
            "empresa_nome": "EMPRESA EXEMPLO LTDA",
            "cnpj_raiz_2": null,
            "empresa_nome_2": null,
            "descricao": "Parlamentar sócio da empresa desde 20/05/2019",
            "correspondencia": "fraca",
            "regra": "Parlamentar sócio (pessoa física) de empresa que aparece nos dados; senador só pelo nome"
          }
        ]
      }
    }
  }
}
```

`site/exemplos/alertas/cota_fornecedor_sancionado/1.json`:

```json
{
  "esquema": 1,
  "tipo": "cota_fornecedor_sancionado",
  "pagina": 1,
  "paginas": 1,
  "total": 1,
  "alertas": [
    {
      "alerta_id": "7c1e0d2a9f4b4e6a8d3c2b1a0f9e8d7c",
      "tipo": "cota_fornecedor_sancionado",
      "data": "2026-08-14",
      "valor": 1200.0,
      "parlamentar_id": "camara:900001",
      "parlamentar_nome": "ANA EXEMPLO",
      "cnpj_raiz": "11222333",
      "empresa_nome": "EMPRESA EXEMPLO LTDA",
      "cnpj_raiz_2": null,
      "empresa_nome_2": null,
      "descricao": "Despesa de cota com fornecedor sancionado no CEIS por MINISTERIO EXEMPLO desde 01/03/2025",
      "correspondencia": "forte",
      "regra": "Despesa de cota com fornecedor que tinha sanção vigente (CEIS ou CNEP) na data de emissão do documento"
    }
  ]
}
```

- [ ] **Step 4: Escreva os testes do contrato**

`tests/test_site.py`:

```python
"""`coletor site`: contrato (esquemas × exemplos) e gravação dos arquivos do site."""

import json

import pytest

from coletor.site import TIPOS, carregar_validadores, tipo_do_caminho
from tests.amostras import RAIZ

ESQUEMAS = RAIZ / "site" / "esquemas"
EXEMPLOS = RAIZ / "site" / "exemplos"


def _exemplos() -> dict[str, dict]:
    return {
        p.relative_to(EXEMPLOS).as_posix(): json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(EXEMPLOS.rglob("*.json"))
    }


# ---- contrato: exemplos × esquemas


@pytest.mark.parametrize("caminho", sorted(_exemplos()))
def test_exemplo_segue_o_esquema(caminho):
    validadores = carregar_validadores(ESQUEMAS)
    documento = _exemplos()[caminho]
    erros = [e.message for e in validadores[tipo_do_caminho(caminho)].iter_errors(documento)]
    assert erros == []


def test_todo_tipo_de_arquivo_tem_exemplo():
    assert {tipo_do_caminho(c) for c in _exemplos()} == set(TIPOS)


def test_esquema_recusa_campo_que_nao_existe():
    validadores = carregar_validadores(ESQUEMAS)
    documento = _exemplos()["parlamentar/camara-900001.json"]
    documento["cota"]["inventado"] = 1
    assert list(validadores["parlamentar"].iter_errors(documento))


def test_esquema_aceita_cnpj_alfanumerico():
    validadores = carregar_validadores(ESQUEMAS)
    documento = _exemplos()["empresa/112.json"]
    documento["bloco"] = "1AB"
    documento["empresas"] = {"1AB2C3D4": documento["empresas"]["11222333"]}
    assert list(validadores["empresa"].iter_errors(documento)) == []
```

- [ ] **Step 5: Rode e veja falhar**

Run: `uv run pytest tests/test_site.py -q`
Expected: FAIL na coleta, com `ModuleNotFoundError: No module named 'coletor.site'`.

- [ ] **Step 6: Implemente os tipos e os validadores**

`coletor/site.py`:

```python
"""Arquivos do site público (`coletor site`): lê `site_arquivos` do DuckDB, valida e grava em gzip.

Spec: docs/superpowers/specs/2026-10-07-site-publico-design.md, seções 4 e 5. Cada arquivo é
conferido antes de qualquer gravação (caminho, tamanho, CPF completo nos textos e o JSON Schema
do seu tipo) e gravado numa pasta temporária, que só substitui `site/` no fim: se algo falha, o
site anterior fica como estava.
"""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

TIPOS = ("resumo", "busca-parlamentares", "busca-empresas", "parlamentar", "empresa", "alertas")


class ErroSite(Exception):
    """Arquivo do site inválido: nada é gravado."""


def tipo_do_caminho(caminho: str) -> str:
    if caminho == "resumo.json":
        return "resumo"
    if caminho == "busca/parlamentares.json":
        return "busca-parlamentares"
    for prefixo, tipo in (
        ("busca/empresas/", "busca-empresas"),
        ("parlamentar/", "parlamentar"),
        ("empresa/", "empresa"),
        ("alertas/", "alertas"),
    ):
        if caminho.startswith(prefixo):
            return tipo
    raise ErroSite(f"caminho sem tipo conhecido: {caminho}")


def carregar_validadores(pasta: Path) -> dict[str, Draft202012Validator]:
    """Um validador por tipo de arquivo, com `comum.schema.json` disponível para os `$ref`."""
    esquemas = {
        arquivo.name.removesuffix(".schema.json"): json.loads(arquivo.read_text(encoding="utf-8"))
        for arquivo in pasta.glob("*.schema.json")
    }
    faltando = sorted(set(TIPOS) - set(esquemas))
    if faltando:
        raise ErroSite(f"esquemas ausentes em {pasta}: {', '.join(faltando)}")
    registro = Registry().with_resources(
        (esquema["$id"], Resource.from_contents(esquema)) for esquema in esquemas.values()
    )
    return {tipo: Draft202012Validator(esquemas[tipo], registry=registro) for tipo in TIPOS}
```

- [ ] **Step 7: Rode e veja passar**

Run: `uv run pytest tests/test_site.py -q`
Expected: PASS (13 testes: 10 exemplos, todo tipo com exemplo, campo a mais, CNPJ alfanumérico).

- [ ] **Step 8: Prova de mutação**

Em `site/exemplos/parlamentar/senado-900002.json`, dentro de `"alertas"`, troque `"total": 1`
por `"totall": 1`. Run: `uv run pytest tests/test_site.py -q`.
Expected: FAIL em `test_exemplo_segue_o_esquema[parlamentar/senado-900002.json]`. Desfaça
(`git checkout -- site/exemplos/parlamentar/senado-900002.json`) e confirme que volta a passar.

- [ ] **Step 9: Lint e commit**

```bash
uv run ruff check . && uv run ruff format --check .
git add pyproject.toml uv.lock site/esquemas site/exemplos coletor/site.py tests/test_site.py
git commit -m "feat(site): contrato dos arquivos do site (JSON Schemas e exemplos)"
```

---

### Task 2: dbt: pasta `site`, seed dos tipos e `site_alertas`

**Files:**
- Modify: `dbt/dbt_project.yml`
- Create: `dbt/seeds/site_alerta_tipos.csv`
- Create: `dbt/macros/site.sql`
- Create: `dbt/models/site/site_alertas.sql`, `dbt/models/site/site_alertas.yml`

**Interfaces:**
- Consumes: os marts `alerta_*` (exceto `alerta_fonte_reduzida`), `dim_autor_emenda`,
  `dim_parlamentar`; macro `cnpj_raiz` de `dbt/macros/documentos.sql`.
- Produces: tabela `site.site_alertas` com as colunas `alerta_id, tipo, data_fato, valor
  (DECIMAL(38,2)), parlamentar_id, parlamentar_nome, cnpj_raiz, empresa_nome, cnpj_raiz_2,
  empresa_nome_2, descricao, correspondencia ('forte'|'fraca'), regra`; seed
  `site.site_alerta_tipos (tipo, titulo, explicacao, cautela, ordem)`; macros
  `site_alerta_json()`, `site_ordem_alertas()`, `site_data(coluna)`, `site_instante(coluna)`,
  `site_sancao(prefixo)`, `site_origem(coluna)`; variáveis `site_max_alertas`, `site_top`,
  `site_busca_max`, `site_alertas_por_pagina`.

- [ ] **Step 1: Configure a pasta `site`, os seeds e as variáveis**

Em `dbt/dbt_project.yml`, logo depois do bloco `marts:` (depois de `compression: zstd`),
acrescente:

```yaml
    # site público: arquivos JSON montados no SQL (coletor site), só a partir de marts e seeds
    site:
      +schema: site
      +materialized: table

seeds:
  eleitorado:
    +schema: site

vars:
  site_max_alertas: 200 # alertas por parlamentar ou empresa no arquivo (o total vai junto)
  site_top: 20 # itens das listas de maiores fornecedores, favorecidos, autores e órgãos
  site_busca_max: 5000 # empresas num bloco de busca antes de subdividir em 4 letras
  site_alertas_por_pagina: 500
```

- [ ] **Step 2: Crie o seed**

`dbt/seeds/site_alerta_tipos.csv`:

```csv
tipo,titulo,explicacao,cautela,ordem
cota_fornecedor_sancionado,Cota paga a fornecedor sancionado,"O parlamentar foi reembolsado pela cota por uma despesa com fornecedor que, na data da nota, estava no cadastro de punidos da CGU (CEIS ou CNEP).","A cota reembolsa gastos do parlamentar (não é contratação pública), e a sanção pode valer só para o órgão que a aplicou.",1
cota_documento_invalido,Cota com CPF ou CNPJ inválido,A despesa de cota traz um CPF ou CNPJ de fornecedor com tamanho ou dígito verificador errado.,Pode ser só um erro de digitação na prestação de contas.,2
emenda_favorecido_sancionado,Emenda paga a favorecido sancionado,"Um pagamento de emenda parlamentar foi feito a empresa que, na data do pagamento, estava no CEIS ou no CNEP.","A sanção pode valer só para o órgão que a aplicou; o parlamentar indica a emenda, mas quem paga é o órgão executor.",3
contrato_fornecedor_sancionado,Contrato com fornecedor sancionado,"Um contrato federal foi assinado com empresa que, na data da assinatura, estava no CEIS ou no CNEP.",A sanção pode valer só para o órgão que a aplicou.,4
licitacao_vencedor_sancionado,Licitação vencida por sancionado,O vencedor de uma licitação federal estava no CEIS ou no CNEP na data da licitação.,A sanção pode valer só para o órgão que a aplicou.,5
pagamento_empresa_irregular,Pagamento a empresa irregular na Receita,"Despesa de cota, pagamento de emenda ou contrato com empresa que já estava baixada, inapta, suspensa ou nula na Receita na data do fato.",A Receita informa só a situação atual e desde quando ela vale; reativações anteriores não aparecem.,6
empresa_recem_aberta,Empresa recém-aberta,"Contrato ou pagamento de emenda de pelo menos R$ 50 mil, ou despesa de cota de pelo menos R$ 10 mil, com empresa aberta até 180 dias antes.",Empresa nova não é irregular: o alerta só aponta onde vale olhar com mais atenção.,7
licitacao_socios_em_comum,Concorrentes com sócios em comum,Duas empresas que disputaram a mesma licitação tinham pelo menos um sócio em comum desde antes da licitação.,"Os sócios são os da base mais recente da Receita: quem saiu antes não aparece, e ter sócio em comum não prova combinação.",8
parlamentar_socio_fornecedor,Parlamentar sócio de empresa,"O parlamentar aparece como sócio de uma empresa que está nos dados públicos (fornecedor, favorecido ou contratada).","Deputados são identificados pelo nome e por parte do CPF; senadores, só pelo nome, e podem ser homônimos.",9
```

- [ ] **Step 3: Crie as macros**

`dbt/macros/site.sql`:

```sql
{#- Arquivos do site público (spec do site, seção 4). -#}

{#- Um alerta no formato comum do site (seção 4.3), a partir de uma linha de `site_alertas`. -#}
{% macro site_alerta_json() -%}
{
    'alerta_id': alerta_id,
    'tipo': tipo,
    'data': data_fato,
    'valor': valor,
    'parlamentar_id': parlamentar_id,
    'parlamentar_nome': parlamentar_nome,
    'cnpj_raiz': cnpj_raiz,
    'empresa_nome': empresa_nome,
    'cnpj_raiz_2': cnpj_raiz_2,
    'empresa_nome_2': empresa_nome_2,
    'descricao': descricao,
    'correspondencia': correspondencia,
    'regra': regra
}
{%- endmacro %}

{#- Ordem dos alertas em todas as listas do site: do mais recente ao mais antigo. -#}
{% macro site_ordem_alertas() -%}
data_fato desc nulls last, alerta_id
{%- endmacro %}

{% macro site_data(coluna) -%}
strftime({{ coluna }}, '%d/%m/%Y')
{%- endmacro %}

{#- Instante em UTC no formato ISO 8601 (`2026-10-07T10:00:00Z`). -#}
{% macro site_instante(coluna) -%}
strftime({{ coluna }} at time zone 'UTC', '%Y-%m-%dT%H:%M:%SZ')
{%- endmacro %}

{#- Frase dos alertas de sanção: "<prefixo> sancionado no CEIS por <órgão> desde <data>". -#}
{% macro site_sancao(prefixo) -%}
concat(
    {{ prefixo }}, ' sancionado no ', cadastro, ' por ' || orgao_sancionador,
    ' desde ' || {{ site_data('sancao_data_inicio') }}
)
{%- endmacro %}

{% macro site_origem(coluna) -%}
case {{ coluna }}
    when 'cota' then 'Despesa de cota'
    when 'emenda' then 'Pagamento de emenda'
    else 'Contrato'
end
{%- endmacro %}
```

- [ ] **Step 4: Escreva os testes (antes do modelo)**

`dbt/models/site/site_alertas.yml`:

```yaml
version: 2

# Site público (spec docs/superpowers/specs/2026-10-07-site-publico-design.md): modelos que só
# leem marts e seeds, nunca intermediate nem staging.

seeds:
  - name: site_alerta_tipos
    description: Texto em linguagem simples de cada tipo de alerta, mostrado no site.
    columns:
      - name: tipo
        data_tests: [unique, not_null]

models:
  - name: site_alertas
    data_tests:
      - sem_dados_pessoais
      - sem_cpf_completo
    columns:
      - name: alerta_id
        data_tests: [unique, not_null]
      - name: tipo
        data_tests:
          - not_null
          - relationships:
              arguments: {to: ref('site_alerta_tipos'), field: tipo}
      - name: correspondencia
        data_tests:
          - accepted_values:
              arguments: {values: [forte, fraca]}

unit_tests:
  - name: site_alertas_formato_comum
    description: >
      Cada alerta vira o formato comum do site. Sanção casada pela raiz do CNPJ e senador sócio
      só pelo nome saem como correspondência fraca; o parlamentar da emenda vem do autor; o nome
      do parlamentar vem do cadastro quando o alerta não traz; sócios em comum levam as duas
      empresas.
    model: site_alertas
    given:
      - input: ref('alerta_cota_fornecedor_sancionado')
        rows:
          - {alerta_id: a1, tipo_correspondencia: cnpj, parlamentar_id: 'camara:1', nome_beneficiario: ANA, data_emissao: '2026-08-14', valor_reembolsado: 1200, fornecedor_nome: EMPRESA A, fornecedor_documento: '11222333000181', cadastro: CEIS, orgao_sancionador: MINISTERIO X, sancao_data_inicio: '2025-03-01', regra: r}
          - {alerta_id: a2, tipo_correspondencia: cnpj_raiz, parlamentar_id: 'camara:1', nome_beneficiario: ANA, data_emissao: '2026-08-15', valor_reembolsado: 300, fornecedor_nome: EMPRESA A, fornecedor_documento: '11222333000262', cadastro: CEIS, orgao_sancionador: null, sancao_data_inicio: '2025-03-01', regra: r}
      - input: ref('alerta_cota_documento_invalido')
        rows: []
      - input: ref('alerta_emenda_favorecido_sancionado')
        rows:
          - {alerta_id: e1, autor_codigo: '123', fase_despesa: Pagamento, data_documento: '2026-01-10', valor_pago: 5000, favorecido_nome: EMPRESA B, favorecido_documento: '44555666000110', cadastro: CNEP, orgao_sancionador: CGU, sancao_data_inicio: '2024-01-02', tipo_correspondencia: cnpj, regra: r}
      - input: ref('alerta_contrato_fornecedor_sancionado')
        rows: []
      - input: ref('alerta_licitacao_vencedor_sancionado')
        rows: []
      - input: ref('alerta_pagamento_empresa_irregular')
        rows: []
      - input: ref('alerta_empresa_recem_aberta')
        rows:
          - {alerta_id: r1, origem: cota, data_fato: '2024-02-01', valor: 10000, cnpj: '11222333000181', parlamentar_id: 'camara:1', razao_social: EMPRESA A, data_abertura: '2024-01-01', dias_desde_a_abertura: 31, tipo: recem_aberta, regra: r}
      - input: ref('alerta_licitacao_socios_em_comum')
        rows:
          - {alerta_id: s1, orgao_nome: MINISTERIO X, data_licitacao: '2023-05-05', participante_a_cnpj_raiz: '11222333', participante_a_nome: EMPRESA A, participante_b_cnpj_raiz: '44555666', participante_b_nome: EMPRESA B, socios_pessoa_fisica: 1, socios_empresa: 1, regra: r}
      - input: ref('alerta_parlamentar_socio_fornecedor')
        rows:
          - {alerta_id: p1, parlamentar_id: 'senado:2', parlamentar_nome: JOAO, correspondencia: só nome, cnpj_raiz: '11222333', razao_social: EMPRESA A, data_entrada: '2019-05-20', regra: r}
      - input: ref('dim_autor_emenda')
        rows:
          - {autor_codigo: '123', autor_nome: JOAO, parlamentar_id: 'senado:2'}
      - input: ref('dim_parlamentar')
        rows:
          - {parlamentar_id: 'camara:1', nome: ANA}
    expect:
      rows:
        - {alerta_id: a1, tipo: cota_fornecedor_sancionado, parlamentar_id: 'camara:1', parlamentar_nome: ANA, cnpj_raiz: '11222333', cnpj_raiz_2: null, correspondencia: forte, descricao: 'Despesa de cota com fornecedor sancionado no CEIS por MINISTERIO X desde 01/03/2025'}
        - {alerta_id: a2, tipo: cota_fornecedor_sancionado, parlamentar_id: 'camara:1', parlamentar_nome: ANA, cnpj_raiz: '11222333', cnpj_raiz_2: null, correspondencia: fraca, descricao: 'Despesa de cota com fornecedor sancionado no CEIS desde 01/03/2025'}
        - {alerta_id: e1, tipo: emenda_favorecido_sancionado, parlamentar_id: 'senado:2', parlamentar_nome: JOAO, cnpj_raiz: '44555666', cnpj_raiz_2: null, correspondencia: forte, descricao: 'Pagamento de emenda a favorecido sancionado no CNEP por CGU desde 02/01/2024'}
        - {alerta_id: r1, tipo: empresa_recem_aberta, parlamentar_id: 'camara:1', parlamentar_nome: ANA, cnpj_raiz: '11222333', cnpj_raiz_2: null, correspondencia: forte, descricao: 'Despesa de cota com empresa aberta 31 dias antes'}
        - {alerta_id: s1, tipo: licitacao_socios_em_comum, parlamentar_id: null, parlamentar_nome: null, cnpj_raiz: '11222333', cnpj_raiz_2: '44555666', correspondencia: forte, descricao: 'Participantes da mesma licitação de MINISTERIO X com 2 sócio(s) em comum'}
        - {alerta_id: p1, tipo: parlamentar_socio_fornecedor, parlamentar_id: 'senado:2', parlamentar_nome: JOAO, cnpj_raiz: '11222333', cnpj_raiz_2: null, correspondencia: fraca, descricao: 'Parlamentar sócio da empresa desde 20/05/2019'}
```

- [ ] **Step 5: Veja falhar**

Rode o bloco "Como rodar o dbt sobre o lago vazio".
Expected: o `dbt run` falha no parse, porque `site_alertas.yml` cita o modelo `site_alertas`,
que ainda não existe (ou o teste unitário `site_alertas_formato_comum` falha por modelo
ausente).

- [ ] **Step 6: Crie o modelo**

`dbt/models/site/site_alertas.sql`:

```sql
-- Os alertas de fatos num formato comum para o site (spec do site, seção 4.3). Correspondência
-- `fraca`: sanção casada só pela raiz do CNPJ (outra filial) e senador sócio só pelo nome.
-- `alerta_fonte_reduzida` fica de fora: é sobre os dados, não sobre parlamentar ou empresa.
with autores as (
    select autor_codigo, autor_nome, parlamentar_id from {{ ref('dim_autor_emenda') }}
),

alertas as (
    select
        alerta_id,
        'cota_fornecedor_sancionado' as tipo,
        data_emissao as data_fato,
        valor_reembolsado as valor,
        parlamentar_id,
        nome_beneficiario as parlamentar_nome,
        {{ cnpj_raiz('fornecedor_documento') }} as cnpj_raiz,
        fornecedor_nome as empresa_nome,
        cast(null as varchar) as cnpj_raiz_2,
        cast(null as varchar) as empresa_nome_2,
        {{ site_sancao("'Despesa de cota com fornecedor'") }} as descricao,
        if(tipo_correspondencia = 'cnpj_raiz', 'fraca', 'forte') as correspondencia,
        regra
    from {{ ref('alerta_cota_fornecedor_sancionado') }}

    union all
    select
        alerta_id,
        'cota_documento_invalido',
        data_emissao,
        valor_reembolsado,
        parlamentar_id,
        nome_beneficiario,
        null,
        fornecedor_nome,
        null,
        null,
        concat(
            'Despesa de cota com documento de fornecedor inválido (',
            if(motivo = 'tamanho', 'tamanho', 'dígito verificador'), ')'
        ),
        'forte',
        regra
    from {{ ref('alerta_cota_documento_invalido') }}

    union all
    select
        x.alerta_id,
        'emenda_favorecido_sancionado',
        x.data_documento,
        x.valor_pago,
        a.parlamentar_id,
        a.autor_nome,
        {{ cnpj_raiz('x.favorecido_documento') }},
        x.favorecido_nome,
        null,
        null,
        {{ site_sancao("x.fase_despesa || ' de emenda a favorecido'") }},
        if(x.tipo_correspondencia = 'cnpj_raiz', 'fraca', 'forte'),
        x.regra
    from {{ ref('alerta_emenda_favorecido_sancionado') }} as x
    left join autores as a on a.autor_codigo = x.autor_codigo

    union all
    select
        alerta_id,
        'contrato_fornecedor_sancionado',
        data_assinatura,
        valor_final,
        null,
        null,
        {{ cnpj_raiz('fornecedor_documento') }},
        fornecedor_nome,
        null,
        null,
        {{ site_sancao("concat('Contrato', ' de ' || orgao_nome, ' com fornecedor')") }},
        if(tipo_correspondencia = 'cnpj_raiz', 'fraca', 'forte'),
        regra
    from {{ ref('alerta_contrato_fornecedor_sancionado') }}

    union all
    select
        alerta_id,
        'licitacao_vencedor_sancionado',
        data_licitacao,
        null,
        null,
        null,
        {{ cnpj_raiz('participante_documento') }},
        participante_nome,
        null,
        null,
        {{ site_sancao("concat('Vencedor de licitação', ' de ' || orgao_nome)") }},
        if(tipo_correspondencia = 'cnpj_raiz', 'fraca', 'forte'),
        regra
    from {{ ref('alerta_licitacao_vencedor_sancionado') }}

    union all
    select
        alerta_id,
        'pagamento_empresa_irregular',
        data_fato,
        valor,
        parlamentar_id,
        null,
        {{ cnpj_raiz('cnpj') }},
        razao_social,
        null,
        null,
        concat(
            {{ site_origem('origem') }}, ' com empresa ', lower(situacao), ' na Receita desde ',
            {{ site_data('data_situacao') }}
        ),
        'forte',
        regra
    from {{ ref('alerta_pagamento_empresa_irregular') }}

    union all
    select
        alerta_id,
        'empresa_recem_aberta',
        data_fato,
        valor,
        parlamentar_id,
        null,
        {{ cnpj_raiz('cnpj') }},
        razao_social,
        null,
        null,
        if(
            tipo = 'fato_antes_da_abertura',
            concat(
                {{ site_origem('origem') }}, ' anterior à abertura da empresa (',
                {{ site_data('data_abertura') }}, ')'
            ),
            concat(
                {{ site_origem('origem') }}, ' com empresa aberta ', dias_desde_a_abertura,
                ' dias antes'
            )
        ),
        'forte',
        regra
    from {{ ref('alerta_empresa_recem_aberta') }}

    union all
    select
        alerta_id,
        'licitacao_socios_em_comum',
        data_licitacao,
        null,
        null,
        null,
        participante_a_cnpj_raiz,
        participante_a_nome,
        participante_b_cnpj_raiz,
        participante_b_nome,
        concat(
            'Participantes da mesma licitação', ' de ' || orgao_nome, ' com ',
            coalesce(socios_pessoa_fisica, 0) + coalesce(socios_empresa, 0), ' sócio(s) em comum'
        ),
        'forte',
        regra
    from {{ ref('alerta_licitacao_socios_em_comum') }}

    union all
    select
        alerta_id,
        'parlamentar_socio_fornecedor',
        data_entrada,
        null,
        parlamentar_id,
        parlamentar_nome,
        cnpj_raiz,
        razao_social,
        null,
        null,
        concat('Parlamentar sócio da empresa', ' desde ' || {{ site_data('data_entrada') }}),
        if(correspondencia = 'só nome', 'fraca', 'forte'),
        regra
    from {{ ref('alerta_parlamentar_socio_fornecedor') }}
)

select
    a.alerta_id,
    a.tipo,
    a.data_fato,
    cast(a.valor as decimal(38, 2)) as valor,
    a.parlamentar_id,
    coalesce(a.parlamentar_nome, p.nome) as parlamentar_nome,
    a.cnpj_raiz,
    a.empresa_nome,
    a.cnpj_raiz_2,
    a.empresa_nome_2,
    a.descricao,
    a.correspondencia,
    a.regra
from alertas as a
left join {{ ref('dim_parlamentar') }} as p on p.parlamentar_id = a.parlamentar_id
```

- [ ] **Step 7: Veja passar**

Rode de novo o bloco do lago vazio.
Expected: `dbt seed` com `PASS=1`; `dbt run` e `dbt test` sem erro, com
`site_alertas::site_alertas_formato_comum` em PASS, mais os testes de dados de `site_alertas`
(`unique`, `not_null`, `relationships` com o seed, `accepted_values`, `sem_cpf_completo`,
`sem_dados_pessoais`) e do seed.

- [ ] **Step 8: Prova de mutação**

Em `site_alertas.sql`, no primeiro bloco (cota), troque
`if(tipo_correspondencia = 'cnpj_raiz', 'fraca', 'forte')` por
`if(tipo_correspondencia = 'cnpj', 'fraca', 'forte')`. Rode
`uv run dbt test --project-dir dbt --profiles-dir dbt --target ci --select "test_name:site_alertas_formato_comum"`.
Expected: FAIL (as linhas `a1` e `a2` trocam de correspondência). Desfaça e confirme o PASS.

- [ ] **Step 9: Commit**

```bash
git add dbt/dbt_project.yml dbt/seeds dbt/macros/site.sql dbt/models/site
git commit -m "feat(dbt): alertas no formato comum do site e textos dos tipos de alerta"
```

---

### Task 3: dbt: agregados de cota, emendas, contratos e licitações

**Files:**
- Create: `dbt/models/site/site_cota.sql`, `site_emendas.sql`, `site_contratos.sql`,
  `site_licitacoes.sql`, `dbt/models/site/site_agregados.yml`

**Interfaces:**
- Consumes: `fct_despesa_cota_parlamentar` (com `data_emissao_valida`), `fct_emenda_pagamento`,
  `dim_autor_emenda`, `fct_contrato_federal` (com `valor_suspeito`), `fct_licitacao_vencedor`.
- Produces:
  - `site.site_cota (parlamentar_id, ano, categoria, fornecedor_documento, fornecedor_nome,
    fornecedor_cnpj_raiz, valor, despesas)`;
  - `site.site_emendas (parlamentar_id, autor_codigo, autor_nome, ano, favorecido_documento,
    favorecido_nome, favorecido_cnpj_raiz, pago)`;
  - `site.site_contratos (cnpj_raiz, orgao_nome, valor, contratos)`;
  - `site.site_licitacoes (cnpj_raiz, vencidas)`.

- [ ] **Step 1: Escreva os testes**

`dbt/models/site/site_agregados.yml`:

```yaml
version: 2

models:
  - name: site_cota
    data_tests: [sem_dados_pessoais, sem_cpf_completo]
  - name: site_emendas
    data_tests: [sem_dados_pessoais, sem_cpf_completo]
  - name: site_contratos
    data_tests: [sem_dados_pessoais, sem_cpf_completo]
  - name: site_licitacoes
    columns:
      - name: cnpj_raiz
        data_tests: [unique]

unit_tests:
  - name: site_cota_so_do_parlamentar
    description: >
      Soma por parlamentar, ano, categoria e fornecedor. Cota de liderança e despesa com data de
      emissão impossível ficam de fora.
    model: site_cota
    given:
      - input: ref('fct_despesa_cota_parlamentar')
        rows:
          - {parlamentar_id: 'camara:1', tipo_beneficiario: parlamentar, ano: 2025, categoria: COMBUSTIVEIS, fornecedor_documento: '11222333000181', fornecedor_nome: POSTO A, fornecedor_cnpj_raiz: '11222333', valor_reembolsado: 100, data_emissao_valida: true}
          - {parlamentar_id: 'camara:1', tipo_beneficiario: parlamentar, ano: 2025, categoria: COMBUSTIVEIS, fornecedor_documento: '11222333000181', fornecedor_nome: POSTO A, fornecedor_cnpj_raiz: '11222333', valor_reembolsado: 50, data_emissao_valida: true}
          - {parlamentar_id: null, tipo_beneficiario: lideranca, ano: 2025, categoria: COMBUSTIVEIS, fornecedor_documento: '11222333000181', fornecedor_nome: POSTO A, fornecedor_cnpj_raiz: '11222333', valor_reembolsado: 70, data_emissao_valida: true}
          - {parlamentar_id: 'camara:1', tipo_beneficiario: parlamentar, ano: 2025, categoria: COMBUSTIVEIS, fornecedor_documento: '11222333000181', fornecedor_nome: POSTO A, fornecedor_cnpj_raiz: '11222333', valor_reembolsado: 999, data_emissao_valida: false}
    expect:
      rows:
        - {parlamentar_id: 'camara:1', ano: 2025, categoria: COMBUSTIVEIS, fornecedor_cnpj_raiz: '11222333', valor: 150, despesas: 2}

  - name: site_emendas_so_pagamento
    description: >
      Só a fase de pagamento entra; o parlamentar vem do autor da emenda (autor sem parlamentar
      fica com parlamentar nulo).
    model: site_emendas
    given:
      - input: ref('fct_emenda_pagamento')
        rows:
          - {autor_codigo: '123', fase_despesa: Pagamento, data_documento: '2025-03-01', favorecido_documento: '44555666000110', favorecido_nome: EMPRESA B, favorecido_cnpj_raiz: '44555666', valor_pago: 1000}
          - {autor_codigo: '123', fase_despesa: Liquidação, data_documento: '2025-02-01', favorecido_documento: '44555666000110', favorecido_nome: EMPRESA B, favorecido_cnpj_raiz: '44555666', valor_pago: 1000}
          - {autor_codigo: '999', fase_despesa: Pagamento, data_documento: '2025-04-01', favorecido_documento: '44555666000110', favorecido_nome: EMPRESA B, favorecido_cnpj_raiz: '44555666', valor_pago: 500}
      - input: ref('dim_autor_emenda')
        rows:
          - {autor_codigo: '123', autor_nome: JOAO, parlamentar_id: 'senado:2'}
    expect:
      rows:
        - {parlamentar_id: 'senado:2', autor_codigo: '123', autor_nome: JOAO, ano: 2025, pago: 1000}
        - {parlamentar_id: null, autor_codigo: '999', autor_nome: null, ano: 2025, pago: 500}

  - name: site_contratos_sem_valor_suspeito
    description: Contrato com valor implausível e fornecedor que não é CNPJ ficam de fora.
    model: site_contratos
    given:
      - input: ref('fct_contrato_federal')
        rows:
          - {fornecedor_cnpj_raiz: '11222333', fornecedor_tipo_documento: CNPJ, orgao_nome: MINISTERIO X, valor_final: 100, valor_suspeito: false}
          - {fornecedor_cnpj_raiz: '11222333', fornecedor_tipo_documento: CNPJ, orgao_nome: MINISTERIO X, valor_final: 58840000000, valor_suspeito: true}
          - {fornecedor_cnpj_raiz: null, fornecedor_tipo_documento: CPF, orgao_nome: MINISTERIO X, valor_final: 70, valor_suspeito: false}
    expect:
      rows:
        - {cnpj_raiz: '11222333', orgao_nome: MINISTERIO X, valor: 100, contratos: 1}
```

- [ ] **Step 2: Veja falhar**

Rode o bloco do lago vazio.
Expected: falha, porque os modelos citados no `.yml` ainda não existem.

- [ ] **Step 3: Crie os modelos**

`dbt/models/site/site_cota.sql`:

```sql
-- Cota parlamentar agregada para o site (parlamentar, ano, categoria e fornecedor). Só despesas do
-- próprio parlamentar (sem a cota de liderança) e sem data de emissão impossível.
select
    parlamentar_id,
    ano,
    categoria,
    fornecedor_documento,
    max(fornecedor_nome) as fornecedor_nome,
    max(fornecedor_cnpj_raiz) as fornecedor_cnpj_raiz,
    sum(valor_reembolsado) as valor,
    count(*) as despesas
from {{ ref('fct_despesa_cota_parlamentar') }}
where tipo_beneficiario = 'parlamentar' and parlamentar_id is not null and data_emissao_valida
group by parlamentar_id, ano, categoria, fornecedor_documento
```

`dbt/models/site/site_emendas.sql`:

```sql
-- Pagamentos de emendas agregados para o site (autor, ano e favorecido), com o parlamentar quando o
-- autor está ligado a um. Só a fase de pagamento: empenho e liquidação repetiriam o valor.
select
    a.parlamentar_id,
    p.autor_codigo,
    max(a.autor_nome) as autor_nome,
    year(p.data_documento) as ano,
    p.favorecido_documento,
    max(p.favorecido_nome) as favorecido_nome,
    max(p.favorecido_cnpj_raiz) as favorecido_cnpj_raiz,
    sum(p.valor_pago) as pago
from {{ ref('fct_emenda_pagamento') }} as p
left join {{ ref('dim_autor_emenda') }} as a on a.autor_codigo = p.autor_codigo
where p.fase_despesa = 'Pagamento' and p.data_documento is not null
group by a.parlamentar_id, p.autor_codigo, year(p.data_documento), p.favorecido_documento
```

`dbt/models/site/site_contratos.sql`:

```sql
-- Contratos federais por empresa (raiz do CNPJ) e órgão, para o site. Valores implausíveis
-- (`valor_suspeito`) ficam de fora.
select
    fornecedor_cnpj_raiz as cnpj_raiz,
    orgao_nome,
    sum(valor_final) as valor,
    count(*) as contratos
from {{ ref('fct_contrato_federal') }}
where fornecedor_tipo_documento = 'CNPJ' and not valor_suspeito
group by fornecedor_cnpj_raiz, orgao_nome
```

`dbt/models/site/site_licitacoes.sql`:

```sql
-- Licitações federais vencidas por empresa (raiz do CNPJ), para o site.
select
    participante_cnpj_raiz as cnpj_raiz,
    count(distinct licitacao_id) as vencidas
from {{ ref('fct_licitacao_vencedor') }}
where participante_tipo_documento = 'CNPJ'
group by participante_cnpj_raiz
```

- [ ] **Step 4: Veja passar**

Rode o bloco do lago vazio.
Expected: PASS em `site_cota_so_do_parlamentar`, `site_emendas_so_pagamento`,
`site_contratos_sem_valor_suspeito` e nos testes de dados dos quatro modelos.

- [ ] **Step 5: Prova de mutação**

Em `site_cota.sql`, apague `and data_emissao_valida` do `where`. Rode
`uv run dbt run --project-dir dbt --profiles-dir dbt --target ci --select site_cota` e
`uv run dbt test --project-dir dbt --profiles-dir dbt --target ci --select "test_name:site_cota_so_do_parlamentar"`.
Expected: FAIL (o valor vira 1149 e as despesas, 3). Desfaça e confirme o PASS.

- [ ] **Step 6: Commit**

```bash
git add dbt/models/site
git commit -m "feat(dbt): agregados de cota, emendas, contratos e licitações para o site"
```

---

### Task 4: dbt: arquivos de parlamentar e de empresa

**Files:**
- Create: `dbt/models/site/site_arquivos_parlamentar.sql`,
  `dbt/models/site/site_arquivos_empresa.sql`, `dbt/models/site/site_arquivos_entidades.yml`

**Interfaces:**
- Consumes: `site_cota`, `site_emendas`, `site_contratos`, `site_licitacoes`, `site_alertas`
  (tarefas 2 e 3); `dim_parlamentar`, `dim_empresa`, `dim_municipio`, `fct_sancao`; macros
  `site_alerta_json()`, `site_ordem_alertas()`; variáveis `site_max_alertas`, `site_top`.
- Produces:
  - `site.site_arquivos_parlamentar (caminho, conteudo, alertas_total, alertas_no_arquivo,
    fornecedores_no_arquivo)`;
  - `site.site_arquivos_empresa (caminho, conteudo, empresas_no_arquivo, alertas_total,
    alertas_no_arquivo)`.
  - As colunas além de `caminho` e `conteudo` existem para os testes; a tarefa 5 só usa as duas
    primeiras.

- [ ] **Step 1: Escreva os testes**

`dbt/models/site/site_arquivos_entidades.yml`:

```yaml
version: 2

unit_tests:
  - name: site_parlamentar_corta_alertas_e_fornecedores
    description: >
      O arquivo do parlamentar traz os `site_max_alertas` alertas mais recentes com o total, e os
      `site_top` maiores fornecedores. Parlamentar sem dados também tem arquivo.
    model: site_arquivos_parlamentar
    overrides:
      vars: {site_max_alertas: 1, site_top: 2}
    given:
      - input: ref('dim_parlamentar')
        rows:
          - {parlamentar_id: 'camara:1', casa: camara, id_origem: '1', nome: ANA}
          - {parlamentar_id: 'senado:2', casa: senado, id_origem: '2', nome: JOAO}
      - input: ref('site_cota')
        rows:
          - {parlamentar_id: 'camara:1', ano: 2025, categoria: COMBUSTIVEIS, fornecedor_documento: '11222333000181', fornecedor_nome: POSTO A, valor: 300, despesas: 3}
          - {parlamentar_id: 'camara:1', ano: 2025, categoria: COMBUSTIVEIS, fornecedor_documento: '44555666000110', fornecedor_nome: POSTO B, valor: 200, despesas: 2}
          - {parlamentar_id: 'camara:1', ano: 2026, categoria: TELEFONIA, fornecedor_documento: '77888999000100', fornecedor_nome: TELE C, valor: 100, despesas: 1}
      - input: ref('site_emendas')
        rows: []
      - input: ref('site_alertas')
        rows:
          - {alerta_id: a1, tipo: cota_fornecedor_sancionado, data_fato: '2026-01-01', parlamentar_id: 'camara:1', descricao: x, correspondencia: forte, regra: r}
          - {alerta_id: a2, tipo: cota_fornecedor_sancionado, data_fato: '2026-02-01', parlamentar_id: 'camara:1', descricao: x, correspondencia: forte, regra: r}
    expect:
      rows:
        - {caminho: parlamentar/camara-1.json, alertas_total: 2, alertas_no_arquivo: 1, fornecedores_no_arquivo: 2}
        - {caminho: parlamentar/senado-2.json, alertas_total: 0, alertas_no_arquivo: 0, fornecedores_no_arquivo: 0}

  - name: site_empresa_em_blocos_com_socios_nas_duas
    description: >
      Empresas agrupadas pelos 3 primeiros caracteres da raiz (alfanumérica inclusive). O alerta
      de sócios em comum entra no arquivo das duas empresas.
    model: site_arquivos_empresa
    given:
      - input: ref('dim_empresa')
        rows:
          - {cnpj_raiz: '11222333', razao_social: EMPRESA A}
          - {cnpj_raiz: '11299999', razao_social: EMPRESA C}
          - {cnpj_raiz: '44555666', razao_social: EMPRESA B}
          - {cnpj_raiz: '1AB2C3D4', razao_social: EMPRESA ALFANUMERICA}
      - input: ref('dim_municipio')
        rows: []
      - input: ref('dim_parlamentar')
        rows: []
      - input: ref('site_cota')
        rows: []
      - input: ref('site_emendas')
        rows: []
      - input: ref('site_contratos')
        rows: []
      - input: ref('site_licitacoes')
        rows: []
      - input: ref('fct_sancao')
        rows: []
      - input: ref('site_alertas')
        rows:
          - {alerta_id: s1, tipo: licitacao_socios_em_comum, data_fato: '2023-05-05', cnpj_raiz: '11222333', cnpj_raiz_2: '44555666', descricao: x, correspondencia: forte, regra: r}
    expect:
      rows:
        - {caminho: empresa/112.json, empresas_no_arquivo: 2, alertas_total: 1}
        - {caminho: empresa/1AB.json, empresas_no_arquivo: 1, alertas_total: 0}
        - {caminho: empresa/445.json, empresas_no_arquivo: 1, alertas_total: 1}
```

- [ ] **Step 2: Veja falhar**

Rode o bloco do lago vazio.
Expected: falha, porque os modelos ainda não existem.

- [ ] **Step 3: Crie os modelos**

`dbt/models/site/site_arquivos_parlamentar.sql`:

```sql
-- Um arquivo por parlamentar (`parlamentar/<casa>-<id>.json`, spec do site, seção 4.2): cota por
-- ano, por categoria e os 20 maiores fornecedores; emendas de autoria por ano e os 20 maiores
-- favorecidos; alertas (os `site_max_alertas` mais recentes e o total).
with cota as (
    select * from {{ ref('site_cota') }}
),

emendas as (
    select * from {{ ref('site_emendas') }} where parlamentar_id is not null
),

cota_total as (
    select parlamentar_id, sum(valor) as total from cota group by parlamentar_id
),

cota_ano as (
    select parlamentar_id, list({'ano': ano, 'valor': valor} order by ano) as itens
    from (select parlamentar_id, ano, sum(valor) as valor from cota group by parlamentar_id, ano)
    group by parlamentar_id
),

cota_categoria as (
    select
        parlamentar_id,
        list({'categoria': categoria, 'valor': valor} order by valor desc, categoria) as itens
    from (
        select parlamentar_id, categoria, sum(valor) as valor
        from cota group by parlamentar_id, categoria
    )
    group by parlamentar_id
),

cota_fornecedor as (
    select
        parlamentar_id,
        list(
            {
                'nome': nome, 'documento': documento, 'cnpj_raiz': cnpj_raiz, 'valor': valor,
                'despesas': despesas
            }
            order by valor desc, nome
        ) as itens
    from (
        select
            parlamentar_id,
            fornecedor_documento as documento,
            max(fornecedor_nome) as nome,
            max(fornecedor_cnpj_raiz) as cnpj_raiz,
            sum(valor) as valor,
            sum(despesas) as despesas
        from cota
        group by parlamentar_id, fornecedor_documento
        qualify row_number() over (
            partition by parlamentar_id order by sum(valor) desc, max(fornecedor_nome)
        ) <= {{ var('site_top') }}
    )
    group by parlamentar_id
),

emendas_ano as (
    select parlamentar_id, sum(pago) as total, list({'ano': ano, 'pago': pago} order by ano) as itens
    from (
        select parlamentar_id, ano, sum(pago) as pago from emendas group by parlamentar_id, ano
    )
    group by parlamentar_id
),

emendas_favorecido as (
    select
        parlamentar_id,
        list(
            {'nome': nome, 'documento': documento, 'cnpj_raiz': cnpj_raiz, 'pago': pago}
            order by pago desc, nome
        ) as itens
    from (
        select
            parlamentar_id,
            favorecido_documento as documento,
            max(favorecido_nome) as nome,
            max(favorecido_cnpj_raiz) as cnpj_raiz,
            sum(pago) as pago
        from emendas
        group by parlamentar_id, favorecido_documento
        qualify row_number() over (
            partition by parlamentar_id order by sum(pago) desc, max(favorecido_nome)
        ) <= {{ var('site_top') }}
    )
    group by parlamentar_id
),

alertas as (
    select
        parlamentar_id,
        count(*) as total,
        list({{ site_alerta_json() }} order by {{ site_ordem_alertas() }})
            filter (where ordem <= {{ var('site_max_alertas') }}) as itens
    from (
        select
            *,
            row_number() over (
                partition by parlamentar_id order by {{ site_ordem_alertas() }}
            ) as ordem
        from {{ ref('site_alertas') }}
        where parlamentar_id is not null
    )
    group by parlamentar_id
)

select
    'parlamentar/' || replace(p.parlamentar_id, ':', '-') || '.json' as caminho,
    to_json({
        'esquema': 1,
        'parlamentar': {
            'id': p.parlamentar_id,
            'nome': p.nome,
            'casa': p.casa,
            'uf': p.uf_sigla,
            'partido': p.partido_sigla,
            'foto': p.url_foto,
            'legislaturas': coalesce(p.legislaturas, []),
            'url_oficial': if(
                p.casa = 'camara',
                'https://www.camara.leg.br/deputados/' || p.id_origem,
                'https://www25.senado.leg.br/web/senadores/senador/-/perfil/' || p.id_origem
            )
        },
        'cota': {
            'total': coalesce(ct.total, 0),
            'por_ano': coalesce(ca.itens, []),
            'por_categoria': coalesce(cc.itens, []),
            'fornecedores': coalesce(cf.itens, [])
        },
        'emendas': {
            'total_pago': coalesce(ea.total, 0),
            'por_ano': coalesce(ea.itens, []),
            'favorecidos': coalesce(ef.itens, [])
        },
        'alertas': {'total': coalesce(al.total, 0), 'itens': coalesce(al.itens, [])}
    })::varchar as conteudo,
    coalesce(al.total, 0) as alertas_total,
    coalesce(len(al.itens), 0) as alertas_no_arquivo,
    coalesce(len(cf.itens), 0) as fornecedores_no_arquivo
from {{ ref('dim_parlamentar') }} as p
left join cota_total as ct on ct.parlamentar_id = p.parlamentar_id
left join cota_ano as ca on ca.parlamentar_id = p.parlamentar_id
left join cota_categoria as cc on cc.parlamentar_id = p.parlamentar_id
left join cota_fornecedor as cf on cf.parlamentar_id = p.parlamentar_id
left join emendas_ano as ea on ea.parlamentar_id = p.parlamentar_id
left join emendas_favorecido as ef on ef.parlamentar_id = p.parlamentar_id
left join alertas as al on al.parlamentar_id = p.parlamentar_id
```

`dbt/models/site/site_arquivos_empresa.sql`:

```sql
-- Empresas em blocos pelos 3 primeiros caracteres da raiz do CNPJ (`empresa/<abc>.json`, spec do
-- site, seção 4.2): cadastro na Receita (sem sócios, endereço nem contato), o que recebeu (cota,
-- emendas, contratos, licitações vencidas), sanções e alertas. O universo é `dim_empresa`.
with empresas as (
    select e.*, m.municipio_nome
    from {{ ref('dim_empresa') }} as e
    left join {{ ref('dim_municipio') }} as m on m.municipio_id = e.municipio_id
),

cota as (
    select
        c.fornecedor_cnpj_raiz as cnpj_raiz,
        sum(c.valor) as total,
        list(
            {'parlamentar_id': c.parlamentar_id, 'nome': p.nome, 'valor': c.valor}
            order by c.valor desc, c.parlamentar_id
        ) filter (where c.ordem <= {{ var('site_top') }}) as itens
    from (
        select
            fornecedor_cnpj_raiz,
            parlamentar_id,
            sum(valor) as valor,
            row_number() over (
                partition by fornecedor_cnpj_raiz order by sum(valor) desc, parlamentar_id
            ) as ordem
        from {{ ref('site_cota') }}
        where fornecedor_cnpj_raiz is not null
        group by fornecedor_cnpj_raiz, parlamentar_id
    ) as c
    left join {{ ref('dim_parlamentar') }} as p on p.parlamentar_id = c.parlamentar_id
    group by c.fornecedor_cnpj_raiz
),

emendas as (
    select
        favorecido_cnpj_raiz as cnpj_raiz,
        sum(pago) as total,
        list(
            {'autor': autor, 'parlamentar_id': parlamentar_id, 'pago': pago}
            order by pago desc, autor
        ) filter (where ordem <= {{ var('site_top') }}) as itens
    from (
        select
            favorecido_cnpj_raiz,
            max(autor_nome) as autor,
            max(parlamentar_id) as parlamentar_id,
            sum(pago) as pago,
            row_number() over (
                partition by favorecido_cnpj_raiz order by sum(pago) desc, max(autor_nome)
            ) as ordem
        from {{ ref('site_emendas') }}
        where favorecido_cnpj_raiz is not null
        group by favorecido_cnpj_raiz, autor_codigo
    )
    group by favorecido_cnpj_raiz
),

contratos as (
    select
        cnpj_raiz,
        sum(valor) as total,
        sum(contratos) as quantidade,
        list(
            {'orgao': orgao_nome, 'valor': valor, 'contratos': contratos}
            order by valor desc, orgao_nome
        ) filter (where ordem <= {{ var('site_top') }}) as itens
    from (
        select
            *,
            row_number() over (partition by cnpj_raiz order by valor desc, orgao_nome) as ordem
        from {{ ref('site_contratos') }}
    )
    group by cnpj_raiz
),

sancoes as (
    select
        sancionado_cnpj_raiz as cnpj_raiz,
        list(
            {
                'sancao_id': sancao_id, 'cadastro': cadastro, 'categoria': categoria,
                'orgao': orgao_sancionador, 'inicio': data_inicio, 'fim': data_fim,
                'vigente': data_fim is null or data_fim >= current_date
            }
            order by data_inicio desc nulls last, sancao_id
        ) as itens
    from {{ ref('fct_sancao') }}
    where sancionado_cnpj_raiz is not null
    group by sancionado_cnpj_raiz
),

-- o alerta de sócios em comum aparece no arquivo das duas empresas
alertas_por_empresa as (
    select cnpj_raiz as empresa, * from {{ ref('site_alertas') }} where cnpj_raiz is not null
    union all
    select cnpj_raiz_2 as empresa, * from {{ ref('site_alertas') }} where cnpj_raiz_2 is not null
),

alertas as (
    select
        empresa as cnpj_raiz,
        count(*) as total,
        list({{ site_alerta_json() }} order by {{ site_ordem_alertas() }})
            filter (where ordem <= {{ var('site_max_alertas') }}) as itens
    from (
        select
            *,
            row_number() over (partition by empresa order by {{ site_ordem_alertas() }}) as ordem
        from alertas_por_empresa
    )
    group by empresa
),

uma as (
    select
        e.cnpj_raiz,
        {
            'cadastro': {
                'razao_social': e.razao_social,
                'natureza_juridica': e.natureza_juridica,
                'porte': e.porte,
                'capital_social': e.capital_social,
                'abertura': e.data_abertura,
                'situacao': e.situacao,
                'data_situacao': e.data_situacao,
                'motivo_situacao': e.motivo_situacao,
                'atividade': e.cnae_principal_descricao,
                'municipio': e.municipio_nome,
                'uf': e.uf_sigla,
                'optante_simples': e.optante_simples,
                'optante_mei': e.optante_mei,
                'estabelecimentos': e.estabelecimentos,
                'socios': e.socios,
                'matriz_cnpj': e.matriz_cnpj,
                'url_portal': 'https://portaldatransparencia.gov.br/busca?termo=' || e.matriz_cnpj,
                'competencia_receita': e.competencia_receita
            },
            'cota': {'total': coalesce(c.total, 0), 'parlamentares': coalesce(c.itens, [])},
            'emendas': {'total_pago': coalesce(em.total, 0), 'autores': coalesce(em.itens, [])},
            'contratos': {
                'total': coalesce(k.total, 0),
                'quantidade': coalesce(k.quantidade, 0),
                'orgaos': coalesce(k.itens, [])
            },
            'licitacoes': {'vencidas': coalesce(l.vencidas, 0)},
            'sancoes': coalesce(s.itens, []),
            'alertas': {'total': coalesce(a.total, 0), 'itens': coalesce(a.itens, [])}
        } as dados,
        coalesce(a.total, 0) as alertas_total,
        coalesce(len(a.itens), 0) as alertas_no_arquivo
    from empresas as e
    left join cota as c on c.cnpj_raiz = e.cnpj_raiz
    left join emendas as em on em.cnpj_raiz = e.cnpj_raiz
    left join contratos as k on k.cnpj_raiz = e.cnpj_raiz
    left join {{ ref('site_licitacoes') }} as l on l.cnpj_raiz = e.cnpj_raiz
    left join sancoes as s on s.cnpj_raiz = e.cnpj_raiz
    left join alertas as a on a.cnpj_raiz = e.cnpj_raiz
)

select
    'empresa/' || left(cnpj_raiz, 3) || '.json' as caminho,
    to_json({
        'esquema': 1,
        'bloco': left(cnpj_raiz, 3),
        'empresas': map_from_entries(list((cnpj_raiz, dados) order by cnpj_raiz))
    })::varchar as conteudo,
    count(*) as empresas_no_arquivo,
    sum(alertas_total) as alertas_total,
    sum(alertas_no_arquivo) as alertas_no_arquivo
from uma
group by left(cnpj_raiz, 3)
```

- [ ] **Step 4: Veja passar**

Rode o bloco do lago vazio.
Expected: PASS em `site_parlamentar_corta_alertas_e_fornecedores` e
`site_empresa_em_blocos_com_socios_nas_duas`.

- [ ] **Step 5: Prova de mutação**

Em `site_arquivos_empresa.sql`, no CTE `alertas_por_empresa`, apague o `union all` e o segundo
`select` (o da `cnpj_raiz_2`). Rode `dbt run --select site_arquivos_empresa` e
`dbt test --select "test_name:site_empresa_em_blocos_com_socios_nas_duas"` (com
`--project-dir dbt --profiles-dir dbt --target ci`).
Expected: FAIL (o bloco `445` fica com `alertas_total` 0). Desfaça e confirme o PASS.

- [ ] **Step 6: Commit**

```bash
git add dbt/models/site
git commit -m "feat(dbt): arquivos do site por parlamentar e por bloco de empresas"
```

---

### Task 5: dbt: busca, alertas paginados, resumo e `site_arquivos`

**Files:**
- Create: `dbt/models/site/site_arquivos_busca.sql`, `site_arquivos_alertas.sql`,
  `site_arquivos_resumo.sql`, `site_arquivos.sql`, `dbt/models/site/site_arquivos.yml`

**Interfaces:**
- Consumes: tudo das tarefas 2 a 4; `monitor_fontes`, `alerta_fonte_reduzida`,
  `fct_despesa_cota_parlamentar`, `fct_emenda_pagamento`, `fct_contrato_federal`.
- Produces: `site.site_arquivos (caminho VARCHAR, conteudo VARCHAR)`, uma linha por arquivo,
  que o `coletor site` (tarefa 6) lê com `select caminho, conteudo from site.site_arquivos`.

- [ ] **Step 1: Escreva os testes**

`dbt/models/site/site_arquivos.yml`:

```yaml
version: 2

models:
  - name: site_arquivos
    description: Todos os arquivos do site (caminho relativo a site/ e conteúdo JSON).
    columns:
      - name: caminho
        data_tests: [unique, not_null]
      - name: conteudo
        data_tests: [not_null]

unit_tests:
  - name: site_busca_subdivide_blocos_grandes
    description: >
      Palavras comuns (LTDA, EIRELI, SA) e de menos de 3 letras ficam de fora. Com `site_busca_max`
      = 2, o bloco "con" (3 empresas) é subdividido: as de palavra com 4 letras ou mais vão para
      "cons", e a de palavra de exatamente 3 letras fica no "con".
    model: site_arquivos_busca
    overrides:
      vars: {site_busca_max: 2}
    given:
      - input: ref('dim_empresa')
        rows:
          - {cnpj_raiz: '11222333', razao_social: CONSTRUTORA ALFA LTDA, uf_sigla: DF, situacao: ATIVA}
          - {cnpj_raiz: '44555666', razao_social: CONSULTORIA BETA EIRELI, uf_sigla: SP, situacao: ATIVA}
          - {cnpj_raiz: '77888999', razao_social: CON ENGENHARIA SA, uf_sigla: RJ, situacao: BAIXADA}
      - input: ref('dim_parlamentar')
        rows: []
    expect:
      rows:
        - {caminho: busca/empresas/alf.json, subdividido: false, empresas_no_arquivo: 1}
        - {caminho: busca/empresas/bet.json, subdividido: false, empresas_no_arquivo: 1}
        - {caminho: busca/empresas/con.json, subdividido: true, empresas_no_arquivo: 1}
        - {caminho: busca/empresas/cons.json, subdividido: false, empresas_no_arquivo: 2}
        - {caminho: busca/empresas/eng.json, subdividido: false, empresas_no_arquivo: 1}
        - {caminho: busca/parlamentares.json, subdividido: null, empresas_no_arquivo: 0}

  - name: site_alertas_em_paginas
    description: Com `site_alertas_por_pagina` = 2, três alertas do mesmo tipo dão duas páginas.
    model: site_arquivos_alertas
    overrides:
      vars: {site_alertas_por_pagina: 2}
    given:
      - input: ref('site_alertas')
        rows:
          - {alerta_id: a1, tipo: cota_documento_invalido, data_fato: '2026-01-01', descricao: x, correspondencia: forte, regra: r}
          - {alerta_id: a2, tipo: cota_documento_invalido, data_fato: '2026-01-02', descricao: x, correspondencia: forte, regra: r}
          - {alerta_id: a3, tipo: cota_documento_invalido, data_fato: '2026-01-03', descricao: x, correspondencia: forte, regra: r}
    expect:
      rows:
        - {caminho: alertas/cota_documento_invalido/1.json}
        - {caminho: alertas/cota_documento_invalido/2.json}
```

- [ ] **Step 2: Veja falhar**

Rode o bloco do lago vazio.
Expected: falha, porque os modelos ainda não existem.

- [ ] **Step 3: Crie os modelos**

`dbt/models/site/site_arquivos_busca.sql`:

```sql
-- Índice de busca (spec do site, seção 4.2). Parlamentares num arquivo só. Empresas em blocos pelas
-- 3 primeiras letras de cada palavra da razão social (sem acento, minúsculas, 3 ou mais
-- caracteres, fora das palavras comuns); bloco com mais de `site_busca_max` empresas é
-- subdividido em blocos de 4 letras e fica só com as empresas de palavra de exatamente 3 letras.
{%- set comuns = [
    'ltda', 'me', 'epp', 'eireli', 'sa', 's/a', 'cia', 'de', 'da', 'do', 'das', 'dos', 'e',
    'comercio', 'servicos', 'industria',
] %}
with empresas as (
    select cnpj_raiz, razao_social, uf_sigla, situacao from {{ ref('dim_empresa') }}
),

palavras as (
    select distinct cnpj_raiz, palavra
    from (
        select
            cnpj_raiz,
            unnest(
                regexp_split_to_array(
                    lower(strip_accents(coalesce(razao_social, ''))), '[^a-z0-9]+'
                )
            ) as palavra
        from empresas
    )
    where length(palavra) >= 3
        and palavra not in ('{{ comuns | join("', '") }}')
),

contagem as (
    select left(palavra, 3) as prefixo3, count(distinct cnpj_raiz) as empresas
    from palavras
    group by left(palavra, 3)
),

entradas as (
    select distinct
        p.cnpj_raiz,
        if(c.empresas > {{ var('site_busca_max') }}, left(p.palavra, 4), left(p.palavra, 3))
            as prefixo
    from palavras as p
    join contagem as c on c.prefixo3 = left(p.palavra, 3)
),

blocos as (
    select
        n.prefixo,
        list(
            {'raiz': e.cnpj_raiz, 'nome': e.razao_social, 'uf': e.uf_sigla, 'situacao': e.situacao}
            order by e.razao_social, e.cnpj_raiz
        ) as itens
    from entradas as n
    join empresas as e on e.cnpj_raiz = n.cnpj_raiz
    group by n.prefixo
),

subdivididos as (
    select prefixo3 as prefixo from contagem where empresas > {{ var('site_busca_max') }}
),

prefixos as (
    select prefixo from blocos
    union
    select prefixo from subdivididos
)

select
    'busca/empresas/' || x.prefixo || '.json' as caminho,
    to_json({
        'esquema': 1,
        'prefixo': x.prefixo,
        'subdividido': s.prefixo is not null,
        'empresas': coalesce(b.itens, [])
    })::varchar as conteudo,
    s.prefixo is not null as subdividido,
    coalesce(len(b.itens), 0) as empresas_no_arquivo
from prefixos as x
left join blocos as b on b.prefixo = x.prefixo
left join subdivididos as s on s.prefixo = x.prefixo

union all
select
    'busca/parlamentares.json',
    to_json({
        'esquema': 1,
        'parlamentares': coalesce(
            list(
                {
                    'id': parlamentar_id, 'nome': nome, 'casa': casa, 'uf': uf_sigla,
                    'partido': partido_sigla, 'foto': url_foto,
                    'legislaturas': coalesce(legislaturas, [])
                }
                order by nome, parlamentar_id
            ),
            []
        )
    })::varchar,
    null,
    count(*)
from {{ ref('dim_parlamentar') }}
```

`dbt/models/site/site_arquivos_alertas.sql`:

```sql
-- Alertas de cada tipo em páginas de `site_alertas_por_pagina` (`alertas/<tipo>/<n>.json`, spec do
-- site, seção 4.2), do mais recente ao mais antigo. Tipo sem alerta não tem arquivo (o
-- `resumo.json` traz a quantidade 0).
with numerados as (
    select
        *,
        (row_number() over (partition by tipo order by {{ site_ordem_alertas() }}) - 1)
            // {{ var('site_alertas_por_pagina') }} + 1 as pagina,
        count(*) over (partition by tipo) as total
    from {{ ref('site_alertas') }}
)

select
    'alertas/' || tipo || '/' || pagina || '.json' as caminho,
    to_json({
        'esquema': 1,
        'tipo': tipo,
        'pagina': pagina,
        'paginas': cast(ceil(any_value(total) / {{ var('site_alertas_por_pagina') }}) as bigint),
        'total': any_value(total),
        'alertas': list({{ site_alerta_json() }} order by {{ site_ordem_alertas() }})
    })::varchar as conteudo
from numerados
group by tipo, pagina
```

`dbt/models/site/site_arquivos_resumo.sql`:

```sql
-- `resumo.json` (spec do site, seção 4.2): números da capa, tipos de alerta com o texto do seed e a
-- quantidade, os 20 alertas mais recentes de correspondência forte, a situação das fontes e as
-- fontes que encolheram. É o único arquivo com `gerado_em`.
with tipos as (
    select
        t.tipo,
        t.titulo,
        t.explicacao,
        t.cautela,
        t.ordem,
        count(a.alerta_id) as quantidade
    from {{ ref('site_alerta_tipos') }} as t
    left join {{ ref('site_alertas') }} as a on a.tipo = t.tipo
    group by t.tipo, t.titulo, t.explicacao, t.cautela, t.ordem
),

recentes as (
    select *
    from {{ ref('site_alertas') }}
    where correspondencia = 'forte' and data_fato <= current_date
    order by {{ site_ordem_alertas() }}
    limit 20
)

select
    'resumo.json' as caminho,
    to_json({
        'esquema': 1,
        'gerado_em': {{ site_instante('now()') }},
        'dados_ate': {
            'cota': (select max(data_competencia) from {{ ref('fct_despesa_cota_parlamentar') }}),
            'emendas': (
                select max(data_documento) from {{ ref('fct_emenda_pagamento') }}
                where data_documento <= current_date
            ),
            'contratos': (
                select max(data_assinatura) from {{ ref('fct_contrato_federal') }}
                where data_assinatura <= current_date
            ),
            'receita': (select max(competencia_receita) from {{ ref('dim_empresa') }})
        },
        'totais': {
            'cota': (select coalesce(sum(valor), 0) from {{ ref('site_cota') }}),
            'emendas_pago': (select coalesce(sum(pago), 0) from {{ ref('site_emendas') }}),
            'contratos': (select coalesce(sum(valor), 0) from {{ ref('site_contratos') }}),
            'parlamentares': (select count(*) from {{ ref('dim_parlamentar') }}),
            'empresas': (select count(*) from {{ ref('dim_empresa') }})
        },
        'alerta_tipos': (
            select coalesce(
                list(
                    {
                        'tipo': tipo, 'titulo': titulo, 'explicacao': explicacao,
                        'cautela': cautela, 'ordem': ordem, 'quantidade': quantidade
                    }
                    order by ordem
                ),
                []
            )
            from tipos
        ),
        'alertas_recentes': (
            select coalesce(list({{ site_alerta_json() }} order by {{ site_ordem_alertas() }}), [])
            from recentes
        ),
        'fontes': (
            select coalesce(
                list(
                    {
                        'recurso_id': recurso_id,
                        'cadencia': cadencia_corrente,
                        'ultimo_sucesso': {{ site_instante('ultimo_sucesso') }},
                        'status': status_ultima_coleta,
                        'atraso_horas': atraso_horas,
                        'situacao': case
                            when atraso_horas is null or atraso_horas >= limite_erro_horas
                                then 'erro'
                            when atraso_horas >= limite_aviso_horas then 'aviso'
                            else 'ok'
                        end
                    }
                    order by recurso_id
                ),
                []
            )
            from {{ ref('monitor_fontes') }}
        ),
        'fontes_reduzidas': (
            select coalesce(
                list(
                    {
                        'recurso_id': recurso_id,
                        'competencia': competencia,
                        'coletada_em': {{ site_instante('coletada_em') }},
                        'linhas_antes': linhas_antes,
                        'linhas_depois': linhas_depois,
                        'variacao_pct': variacao_pct
                    }
                    order by coletada_em desc, recurso_id
                ),
                []
            )
            from {{ ref('alerta_fonte_reduzida') }}
        )
    })::varchar as conteudo
```

`dbt/models/site/site_arquivos.sql`:

```sql
-- Todos os arquivos do site (`caminho` relativo a `site/`, `conteudo` em JSON), que o
-- `coletor site` valida e grava (spec do site, seções 4 e 5).
select caminho, conteudo from {{ ref('site_arquivos_resumo') }}
union all
select caminho, conteudo from {{ ref('site_arquivos_busca') }}
union all
select caminho, conteudo from {{ ref('site_arquivos_parlamentar') }}
union all
select caminho, conteudo from {{ ref('site_arquivos_empresa') }}
union all
select caminho, conteudo from {{ ref('site_arquivos_alertas') }}
```

- [ ] **Step 4: Veja passar**

Rode o bloco do lago vazio.
Expected: PASS em `site_busca_subdivide_blocos_grandes`, `site_alertas_em_paginas`,
`unique`/`not_null` de `site_arquivos.caminho`. Sobre o lago vazio, `site_arquivos` tem duas
linhas, `resumo.json` e `busca/parlamentares.json`:

```powershell
uv run python -c "import duckdb; c = duckdb.connect('dbt/tests/lago_vazio/ci.duckdb', read_only=True); print(c.execute('select caminho from site.site_arquivos order by 1').fetchall())"
```

Expected: `[('busca/parlamentares.json',), ('resumo.json',)]`.

- [ ] **Step 5: Prova de mutação**

Em `site_arquivos_busca.sql`, no CTE `entradas`, troque `left(p.palavra, 4)` por
`left(p.palavra, 3)`. Rode `dbt run --select site_arquivos_busca` e
`dbt test --select "test_name:site_busca_subdivide_blocos_grandes"`.
Expected: FAIL (`cons.json` some e `con.json` fica com 3 empresas). Desfaça e confirme o PASS.

- [ ] **Step 6: Commit**

```bash
git add dbt/models/site
git commit -m "feat(dbt): busca, alertas paginados e resumo do site"
```

---

### Task 6: `coletor site`

**Files:**
- Modify: `coletor/site.py` (substitua o conteúdo inteiro)
- Modify: `coletor/cli.py`
- Modify: `tests/test_site.py` (substitua o conteúdo inteiro)

**Interfaces:**
- Consumes: `site.site_arquivos` (tarefa 5); `TIPOS`, `tipo_do_caminho`,
  `carregar_validadores` (tarefa 1); `coletor.dbt.banco_do_target(lago, target)`.
- Produces: `coletor.site.gerar_site(banco: Path, publico: Path, esquemas: Path, *,
  limite_descomprimido: int = 2_000_000, limite_gzip: int = 500_000) -> int` (quantidade de
  arquivos); comando `coletor [--target T] site [--esquemas PASTA]`, que grava
  `ELEITORADO_PUBLICO/site/` e sai com 0 ou 1, sem precisar das variáveis do GCP.

- [ ] **Step 1: Escreva os testes**

Substitua `tests/test_site.py` por (os testes do contrato da tarefa 1 continuam, mais os de
`gerar_site` e do comando):

```python
"""`coletor site`: contrato (esquemas × exemplos) e gravação dos arquivos do site."""

import gzip
import json
from pathlib import Path

import duckdb
import pytest

from coletor.site import TIPOS, ErroSite, carregar_validadores, gerar_site, tipo_do_caminho
from tests.amostras import RAIZ

ESQUEMAS = RAIZ / "site" / "esquemas"
EXEMPLOS = RAIZ / "site" / "exemplos"


def _exemplos() -> dict[str, dict]:
    return {
        p.relative_to(EXEMPLOS).as_posix(): json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(EXEMPLOS.rglob("*.json"))
    }


def _banco(tmp_path: Path, arquivos: dict[str, object]) -> Path:
    banco = tmp_path / "eleitorado.duckdb"
    con = duckdb.connect(str(banco))
    con.execute(
        "create schema site; create table site.site_arquivos (caminho varchar, conteudo varchar)"
    )
    for caminho, documento in arquivos.items():
        conteudo = (
            documento if isinstance(documento, str) else json.dumps(documento, ensure_ascii=False)
        )
        con.execute("insert into site.site_arquivos values (?, ?)", [caminho, conteudo])
    con.close()
    return banco


def _ler(publico: Path, caminho: str) -> dict:
    return json.loads(gzip.decompress((publico / "site" / caminho).read_bytes()))


# ---- contrato: exemplos × esquemas


@pytest.mark.parametrize("caminho", sorted(_exemplos()))
def test_exemplo_segue_o_esquema(caminho):
    validadores = carregar_validadores(ESQUEMAS)
    documento = _exemplos()[caminho]
    erros = [e.message for e in validadores[tipo_do_caminho(caminho)].iter_errors(documento)]
    assert erros == []


def test_todo_tipo_de_arquivo_tem_exemplo():
    assert {tipo_do_caminho(c) for c in _exemplos()} == set(TIPOS)


def test_esquema_recusa_campo_que_nao_existe():
    validadores = carregar_validadores(ESQUEMAS)
    documento = _exemplos()["parlamentar/camara-900001.json"]
    documento["cota"]["inventado"] = 1
    assert list(validadores["parlamentar"].iter_errors(documento))


def test_esquema_aceita_cnpj_alfanumerico():
    validadores = carregar_validadores(ESQUEMAS)
    documento = _exemplos()["empresa/112.json"]
    documento["bloco"] = "1AB"
    documento["empresas"] = {"1AB2C3D4": documento["empresas"]["11222333"]}
    assert list(validadores["empresa"].iter_errors(documento)) == []


# ---- gerar_site


def test_grava_os_arquivos_em_gzip_deterministico(tmp_path):
    exemplos = _exemplos()
    banco = _banco(tmp_path, exemplos)
    publico = tmp_path / "publico"

    assert gerar_site(banco, publico, ESQUEMAS) == len(exemplos)
    primeiro = (publico / "site" / "resumo.json").read_bytes()
    assert _ler(publico, "resumo.json") == exemplos["resumo.json"]
    assert _ler(publico, "empresa/112.json") == exemplos["empresa/112.json"]

    gerar_site(banco, publico, ESQUEMAS)
    assert (publico / "site" / "resumo.json").read_bytes() == primeiro
    assert not (publico / "site.novo").exists()


def test_apaga_arquivo_que_deixou_de_existir(tmp_path):
    publico = tmp_path / "publico"
    antigo = publico / "site" / "empresa" / "999.json"
    antigo.parent.mkdir(parents=True)
    antigo.write_bytes(b"x")
    gerar_site(_banco(tmp_path, _exemplos()), publico, ESQUEMAS)
    assert not antigo.exists()


def test_cpf_completo_num_texto_impede_tudo_sem_mostrar_o_cpf(tmp_path):
    publico = tmp_path / "publico"
    (publico / "site").mkdir(parents=True)
    (publico / "site" / "resumo.json").write_bytes(b"anterior")
    arquivos = _exemplos()
    arquivos["busca/empresas/emp.json"]["empresas"][0]["nome"] = "JOSE DA SILVA 12345678909"

    with pytest.raises(ErroSite, match="busca/empresas/emp.json") as erro:
        gerar_site(_banco(tmp_path, arquivos), publico, ESQUEMAS)

    assert "12345678909" not in str(erro.value)
    assert (publico / "site" / "resumo.json").read_bytes() == b"anterior"
    assert not (publico / "site.novo").exists()


def test_valor_com_onze_digitos_e_chave_id_nao_sao_cpf(tmp_path):
    arquivos = _exemplos()
    arquivos["resumo.json"]["totais"]["contratos"] = 12345678901.23
    arquivos["resumo.json"]["alertas_recentes"][0]["alerta_id"] = "55915857505bc16506014ca3f3d755ec"
    gerar_site(_banco(tmp_path, arquivos), tmp_path / "publico", ESQUEMAS)


def test_arquivo_fora_do_esquema(tmp_path):
    arquivos = _exemplos()
    arquivos["resumo.json"]["inventado"] = True
    with pytest.raises(ErroSite, match=r"resumo.json: fora do esquema"):
        gerar_site(_banco(tmp_path, arquivos), tmp_path / "publico", ESQUEMAS)


@pytest.mark.parametrize("caminho", ["../fora.json", "parlamentar/../x.json", "/abs.json"])
def test_caminho_invalido(tmp_path, caminho):
    arquivos = _exemplos()
    arquivos[caminho] = arquivos["resumo.json"]
    with pytest.raises(ErroSite):
        gerar_site(_banco(tmp_path, arquivos), tmp_path / "publico", ESQUEMAS)


def test_arquivo_grande_demais(tmp_path):
    with pytest.raises(ErroSite, match="gzip"):
        gerar_site(_banco(tmp_path, _exemplos()), tmp_path / "publico", ESQUEMAS, limite_gzip=100)


def test_sem_resumo_falha(tmp_path):
    arquivos = _exemplos()
    del arquivos["resumo.json"]
    with pytest.raises(ErroSite, match="resumo"):
        gerar_site(_banco(tmp_path, arquivos), tmp_path / "publico", ESQUEMAS)


def test_sem_banco_falha(tmp_path):
    with pytest.raises(ErroSite, match="rode o dbt"):
        gerar_site(tmp_path / "nao_existe.duckdb", tmp_path / "publico", ESQUEMAS)


def test_bloco_de_cnpj_alfanumerico(tmp_path):
    arquivos = _exemplos()
    empresa = arquivos.pop("empresa/112.json")
    empresa["bloco"] = "1AB"
    empresa["empresas"] = {"1AB2C3D4": empresa["empresas"]["11222333"]}
    arquivos["empresa/1AB.json"] = empresa
    publico = tmp_path / "publico"
    gerar_site(_banco(tmp_path, arquivos), publico, ESQUEMAS)
    assert _ler(publico, "empresa/1AB.json")["bloco"] == "1AB"


# ---- comando `coletor site`


def test_comando_site_nao_precisa_de_credenciais(tmp_path):
    from coletor.cli import main

    lago = tmp_path / "lago"
    lago.mkdir()
    banco = _banco(tmp_path, _exemplos())
    banco.rename(lago / "ci.duckdb")
    publico = tmp_path / "publico"
    codigo = main(
        ["--target", "ci", "site", "--esquemas", str(ESQUEMAS)],
        env={"ELEITORADO_LAGO": str(lago), "ELEITORADO_PUBLICO": str(publico)},
    )
    assert codigo == 0
    assert _ler(publico, "resumo.json")["esquema"] == 1


def test_comando_site_com_erro_sai_com_1(tmp_path):
    from coletor.cli import main

    codigo = main(
        ["site", "--esquemas", str(ESQUEMAS)],
        env={"ELEITORADO_LAGO": str(tmp_path), "ELEITORADO_PUBLICO": str(tmp_path / "p")},
    )
    assert codigo == 1
```

- [ ] **Step 2: Veja falhar**

Run: `uv run pytest tests/test_site.py -q`
Expected: FAIL na coleta, com `ImportError: cannot import name 'gerar_site'`.

- [ ] **Step 3: Implemente `gerar_site`**

Substitua o conteúdo de `coletor/site.py` por:

```python
"""Arquivos do site público (`coletor site`): lê `site_arquivos` do DuckDB, valida e grava em gzip.

Spec: docs/superpowers/specs/2026-10-07-site-publico-design.md, seções 4 e 5. Cada arquivo é
conferido antes de qualquer gravação (caminho, tamanho, CPF completo nos textos e o JSON Schema
do seu tipo) e gravado numa pasta temporária, que só substitui `site/` no fim: se algo falha, o
site anterior fica como estava.
"""

from __future__ import annotations

import gzip
import json
import re
import shutil
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

TIPOS = ("resumo", "busca-parlamentares", "busca-empresas", "parlamentar", "empresa", "alertas")
OBRIGATORIOS = ("resumo", "busca-parlamentares")
LIMITE_DESCOMPRIMIDO = 2_000_000
LIMITE_GZIP = 500_000
# os blocos de empresa e de busca de empresa são milhares: o esquema é conferido numa amostra
AMOSTRADOS = ("empresa", "busca-empresas")
AMOSTRA = 20
CAMINHO = re.compile(r"^[A-Za-z0-9_-]+(/[A-Za-z0-9_-]+)*\.json$")
# o mesmo padrão do teste `sem_cpf_completo` do dbt
CPF = re.compile(r"(^|[^0-9])[0-9]{3}\.?[0-9]{3}\.?[0-9]{3}-?[0-9]{2}([^0-9]|$)")


class ErroSite(Exception):
    """Arquivo do site inválido: nada é gravado."""


def tipo_do_caminho(caminho: str) -> str:
    if caminho == "resumo.json":
        return "resumo"
    if caminho == "busca/parlamentares.json":
        return "busca-parlamentares"
    for prefixo, tipo in (
        ("busca/empresas/", "busca-empresas"),
        ("parlamentar/", "parlamentar"),
        ("empresa/", "empresa"),
        ("alertas/", "alertas"),
    ):
        if caminho.startswith(prefixo):
            return tipo
    raise ErroSite(f"caminho sem tipo conhecido: {caminho}")


def carregar_validadores(pasta: Path) -> dict[str, Draft202012Validator]:
    """Um validador por tipo de arquivo, com `comum.schema.json` disponível para os `$ref`."""
    esquemas = {
        arquivo.name.removesuffix(".schema.json"): json.loads(arquivo.read_text(encoding="utf-8"))
        for arquivo in pasta.glob("*.schema.json")
    }
    faltando = sorted(set(TIPOS) - set(esquemas))
    if faltando:
        raise ErroSite(f"esquemas ausentes em {pasta}: {', '.join(faltando)}")
    registro = Registry().with_resources(
        (esquema["$id"], Resource.from_contents(esquema)) for esquema in esquemas.values()
    )
    return {tipo: Draft202012Validator(esquemas[tipo], registry=registro) for tipo in TIPOS}


def _textos(valor: Any) -> Iterator[str]:
    """Os textos do JSON, menos os das chaves `*_id` (como o teste `sem_cpf_completo` do dbt:
    um MD5 pode começar com 11 dígitos)."""
    if isinstance(valor, str):
        yield valor
    elif isinstance(valor, dict):
        for chave, item in valor.items():
            if not chave.endswith("_id"):
                yield from _textos(item)
    elif isinstance(valor, list):
        for item in valor:
            yield from _textos(item)


def _conferir(
    caminho: str,
    conteudo: str,
    validador: Draft202012Validator | None,
    limite_descomprimido: int,
    limite_gzip: int,
) -> bytes:
    """Confere um arquivo e devolve o conteúdo em gzip (determinístico: `mtime=0`)."""
    if not CAMINHO.match(caminho):
        raise ErroSite(f"caminho inválido: {caminho!r}")
    dados = conteudo.encode("utf-8")
    if len(dados) > limite_descomprimido:
        raise ErroSite(f"{caminho}: {len(dados)} bytes (limite {limite_descomprimido})")
    comprimido = gzip.compress(dados, compresslevel=9, mtime=0)
    if len(comprimido) > limite_gzip:
        raise ErroSite(f"{caminho}: {len(comprimido)} bytes em gzip (limite {limite_gzip})")
    documento = json.loads(conteudo)
    # a mensagem não traz o texto: o log do Actions é público
    if any(CPF.search(texto) for texto in _textos(documento)):
        raise ErroSite(f"{caminho}: CPF completo num texto")
    if validador is not None:
        erro = next(iter(sorted(validador.iter_errors(documento), key=lambda e: e.json_path)), None)
        if erro is not None:
            raise ErroSite(f"{caminho}: fora do esquema em {erro.json_path}: {erro.message}")
    return comprimido


def _trocar(novo: Path, destino: Path) -> None:
    """Põe `novo` no lugar de `destino`. No Windows, a pasta recém-apagada às vezes fica presa por
    um instante (antivírus, indexador): tenta de novo algumas vezes."""
    if destino.exists():
        shutil.rmtree(destino)
    for tentativa in range(5):
        try:
            novo.rename(destino)
            return
        except PermissionError:
            if tentativa == 4:
                raise
            time.sleep(0.2 * (tentativa + 1))


def gerar_site(
    banco: Path,
    publico: Path,
    esquemas: Path,
    *,
    limite_descomprimido: int = LIMITE_DESCOMPRIMIDO,
    limite_gzip: int = LIMITE_GZIP,
) -> int:
    """Grava `publico/site/<caminho>` (JSON em gzip) a partir de `site.site_arquivos` do banco."""
    import duckdb

    validadores = carregar_validadores(esquemas)
    if not banco.exists():
        raise ErroSite(f"{banco} não existe: rode o dbt antes")
    destino = publico / "site"
    novo = publico / "site.novo"
    if novo.exists():
        shutil.rmtree(novo)
    vistos: dict[str, int] = {}
    con = duckdb.connect(str(banco), read_only=True)
    try:
        cursor = con.execute("select caminho, conteudo from site.site_arquivos order by caminho")
        while lote := cursor.fetchmany(500):
            for caminho, conteudo in lote:
                tipo = tipo_do_caminho(caminho)
                vistos[tipo] = vistos.get(tipo, 0) + 1
                amostrado = tipo in AMOSTRADOS and vistos[tipo] > AMOSTRA
                comprimido = _conferir(
                    caminho,
                    conteudo,
                    None if amostrado else validadores[tipo],
                    limite_descomprimido,
                    limite_gzip,
                )
                arquivo = novo / caminho
                arquivo.parent.mkdir(parents=True, exist_ok=True)
                arquivo.write_bytes(comprimido)
        faltando = [tipo for tipo in OBRIGATORIOS if tipo not in vistos]
        if faltando:
            raise ErroSite(f"sem arquivo de {', '.join(faltando)}")
    except BaseException:
        shutil.rmtree(novo, ignore_errors=True)
        raise
    finally:
        con.close()
    _trocar(novo, destino)
    return sum(vistos.values())
```

- [ ] **Step 4: Comando `site` na CLI**

Em `coletor/cli.py`, troque:

```python
    sub.add_parser("publicar", help="gera a linhagem e envia marts e linhagem ao bucket público")
```

por:

```python
    site = sub.add_parser("site", help="gera os arquivos do site público a partir do dbt")
    site.add_argument(
        "--esquemas", type=Path, default=Path("site/esquemas"), help="JSON Schemas do site"
    )

    sub.add_parser("publicar", help="gera a linhagem e envia marts, linhagem e site ao R2")
```

Antes de `def _reconstruir(`, acrescente:

```python
def _site(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    """Lê o banco do dbt e grava `ELEITORADO_PUBLICO/site`; não usa o GCP."""
    from coletor.site import ErroSite, gerar_site

    lago = Path(env.get("ELEITORADO_LAGO", "dados"))
    publico = Path(env.get("ELEITORADO_PUBLICO", "dados/publico"))
    try:
        quantidade = gerar_site(banco_do_target(lago, args.target), publico, args.esquemas)
    except ErroSite as erro:
        log.error("site não gerado: %s", erro)
        return 1
    log.info("site: %d arquivo(s) em %s", quantidade, publico / "site")
    return 0
```

E em `main`, logo depois de `env = os.environ if env is None else env`:

```python
    if args.comando == "site":
        return _site(args, env)
```

- [ ] **Step 5: Veja passar**

Run: `uv run pytest tests/test_site.py -q`
Expected: PASS (todos, inclusive os 13 da tarefa 1).

- [ ] **Step 6: Rode sobre o lago vazio**

Com o lago vazio já gerado (tarefa 5) e as variáveis do bloco do lago vazio:

```powershell
uv run coletor --target ci site
```

Expected: `site: 2 arquivo(s) em …\publico-ci\site`, código 0.

- [ ] **Step 7: Prova de mutação**

Em `coletor/site.py`, na função `_textos`, troque `if not chave.endswith("_id"):` por
`if True:`. Run: `uv run pytest tests/test_site.py -q -k onze_digitos`.
Expected: FAIL (o MD5 que começa com 11 dígitos acusa CPF). Desfaça e confirme o PASS.

- [ ] **Step 8: Lint, suíte e commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest -q
git add coletor/site.py coletor/cli.py tests/test_site.py
git commit -m "feat(coletor): coletor site valida e grava os arquivos do site em gzip"
```

---

### Task 7: `publicar` incremental, com o site em gzip

**Files:**
- Modify: `coletor/publicacao.py` (substitua o conteúdo inteiro)
- Modify: `tests/test_publicacao.py` (substitua o conteúdo inteiro)

**Interfaces:**
- Consumes: `publico/site/*.json` em gzip (tarefa 6).
- Produces: `Publicador.listar() -> dict[str, str]` (chave → ETag);
  `Publicador.enviar(origem, chave, tipo, codificacao=None, cache=None)`;
  `ResumoPublicacao(enviados, apagados, inalterados=0)`; `CACHE_SITE`; `PERMITIDOS` com `site/`.

- [ ] **Step 1: Escreva os testes**

Substitua `tests/test_publicacao.py` por:

```python
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from coletor.publicacao import CACHE_SITE, ErroPublicacao, publicar

AGORA = datetime(2026, 10, 4, 10, tzinfo=UTC)


class FakePublicador:
    """Bucket em memória: guarda o conteúdo e devolve o MD5 como ETag, como o R2."""

    def __init__(self, existentes: dict[str, bytes] | None = None) -> None:
        self.objetos: dict[str, bytes] = dict(existentes or {})
        self.atributos: dict[str, tuple[str, str | None, str | None]] = {}
        self.ordem: list[tuple[str, str]] = []
        self.manifesto: dict | None = None

    def listar(self) -> dict[str, str]:
        return {chave: hashlib.md5(dados).hexdigest() for chave, dados in self.objetos.items()}

    def enviar(self, origem, chave, tipo, codificacao=None, cache=None) -> None:
        self.ordem.append(("enviar", chave))
        self.objetos[chave] = Path(origem).read_bytes()
        self.atributos[chave] = (tipo, codificacao, cache)
        if chave == "manifesto.json":
            self.manifesto = json.loads(self.objetos[chave])

    def apagar(self, chave: str) -> None:
        self.ordem.append(("apagar", chave))
        self.objetos.pop(chave, None)

    @property
    def chaves(self) -> set[str]:
        return set(self.objetos)


@pytest.fixture
def publico(tmp_path):
    raiz = tmp_path / "publico"
    (raiz / "marts" / "fct" / "casa=camara").mkdir(parents=True)
    pq.write_table(pa.table({"a": [1, 2, 3]}), raiz / "marts" / "dim_uf.parquet")
    pq.write_table(pa.table({"a": [1]}), raiz / "marts" / "fct" / "casa=camara" / "d.parquet")
    (raiz / "linhagem").mkdir()
    (raiz / "linhagem" / "index.html").write_text("<html></html>")
    return raiz


def _site(publico: Path, arquivos: dict[str, bytes]) -> None:
    for caminho, dados in arquivos.items():
        destino = publico / "site" / caminho
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(dados)


def test_envia_marts_e_linhagem_e_o_manifesto_por_ultimo(publico):
    publicador = FakePublicador()
    resumo = publicar(publicador, publico, AGORA, "abc123")
    assert publicador.ordem[-1] == ("enviar", "manifesto.json")
    assert resumo.enviados == 4
    arquivos = {a["caminho"]: a for a in publicador.manifesto["arquivos"]}
    assert set(arquivos) == {
        "linhagem/index.html",
        "marts/dim_uf.parquet",
        "marts/fct/casa=camara/d.parquet",
    }
    assert arquivos["marts/dim_uf.parquet"]["linhas"] == 3
    assert arquivos["linhagem/index.html"]["linhas"] is None
    assert len(arquivos["marts/dim_uf.parquet"]["sha256"]) == 64
    assert publicador.manifesto["versao"] == "abc123"


def test_apaga_o_que_deixou_de_existir_depois_do_manifesto(publico):
    publicador = FakePublicador({"marts/antigo.parquet": b"x", "manifesto.json": b"{}"})
    resumo = publicar(publicador, publico, AGORA, "v")
    assert resumo.apagados == 1
    posicao_manifesto = publicador.ordem.index(("enviar", "manifesto.json"))
    assert publicador.ordem.index(("apagar", "marts/antigo.parquet")) > posicao_manifesto
    assert "manifesto.json" in publicador.chaves


def test_arquivo_fora_dos_caminhos_permitidos_impede_a_publicacao(publico):
    (publico / "raw").mkdir()
    (publico / "raw" / "cpfs.parquet").write_bytes(b"x")
    publicador = FakePublicador()
    with pytest.raises(ErroPublicacao, match="raw/cpfs.parquet"):
        publicar(publicador, publico, AGORA, "v")
    assert publicador.ordem == []


def test_sem_marts_nada_e_publicado(tmp_path):
    vazio = tmp_path / "publico"
    (vazio / "linhagem").mkdir(parents=True)
    (vazio / "linhagem" / "index.html").write_text("x")
    publicador = FakePublicador({"marts/dim_uf.parquet": b"x"})
    with pytest.raises(ErroPublicacao, match="nenhum mart"):
        publicar(publicador, vazio, AGORA, "v")
    assert publicador.ordem == []


def test_so_envia_o_que_mudou(publico):
    publicador = FakePublicador()
    publicar(publicador, publico, AGORA, "v")
    publicador.ordem.clear()
    (publico / "linhagem" / "index.html").write_text("<html>nova</html>")

    resumo = publicar(publicador, publico, AGORA, "v")

    assert publicador.ordem == [("enviar", "linhagem/index.html"), ("enviar", "manifesto.json")]
    assert resumo.enviados == 2
    assert resumo.inalterados == 2


def test_site_vai_em_gzip_com_cache_e_fica_fora_do_manifesto(publico):
    _site(publico, {"resumo.json": b"\x1f\x8b gzip"})
    publicador = FakePublicador()
    publicar(publicador, publico, AGORA, "v")
    assert publicador.atributos["site/resumo.json"] == ("application/json", "gzip", CACHE_SITE)
    assert publicador.atributos["marts/dim_uf.parquet"][1:] == (None, None)
    caminhos = {a["caminho"] for a in publicador.manifesto["arquivos"]}
    assert not any(c.startswith("site/") for c in caminhos)


def test_sem_site_local_o_site_do_bucket_fica(publico):
    publicador = FakePublicador({"site/resumo.json": b"anterior", "marts/antigo.parquet": b"x"})
    resumo = publicar(publicador, publico, AGORA, "v")
    assert publicador.objetos["site/resumo.json"] == b"anterior"
    assert "marts/antigo.parquet" not in publicador.chaves
    assert resumo.apagados == 1


def test_com_site_local_apaga_o_arquivo_de_site_que_sumiu(publico):
    _site(publico, {"resumo.json": b"novo"})
    publicador = FakePublicador({"site/resumo.json": b"anterior", "site/empresa/999.json": b"x"})
    publicar(publicador, publico, AGORA, "v")
    assert publicador.objetos["site/resumo.json"] == b"novo"
    assert "site/empresa/999.json" not in publicador.chaves


def test_etag_que_nao_e_md5_faz_reenviar(publico):
    # objeto enviado antes em multipart: o ETag ("<hash>-<partes>") nunca bate com o MD5
    class Multipart(FakePublicador):
        def listar(self) -> dict[str, str]:
            return {chave: "abc-2" for chave in self.objetos}

    publicador = Multipart()
    publicar(publicador, publico, AGORA, "v")
    publicador.ordem.clear()
    publicar(publicador, publico, AGORA, "v")
    assert ("enviar", "marts/dim_uf.parquet") in publicador.ordem
```

- [ ] **Step 2: Veja falhar**

Run: `uv run pytest tests/test_publicacao.py -q`
Expected: FAIL na coleta, com `ImportError: cannot import name 'CACHE_SITE'`.

- [ ] **Step 3: Implemente**

Substitua `coletor/publicacao.py` por:

```python
"""Publicação dos marts, da linhagem e do site no bucket público (Cloudflare R2, API do S3)."""

from __future__ import annotations

import hashlib
import json
import logging
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

log = logging.getLogger(__name__)

PERMITIDOS = ("marts/", "linhagem/", "site/")
SITE = "site/"
MANIFESTO = "manifesto.json"
TIPOS = {
    ".parquet": "application/vnd.apache.parquet",
    ".html": "text/html; charset=utf-8",
    ".json": "application/json",
}
# os JSON do site já estão em gzip (coletor site): o navegador descomprime pelo Content-Encoding
CACHE_SITE = "public, max-age=600"


class ErroPublicacao(Exception):
    """Arquivo fora de marts/, linhagem/ e site/: nada é publicado."""


class Publicador(Protocol):
    def listar(self) -> dict[str, str]:
        """Chave → ETag (o MD5 do conteúdo, sem aspas, em uploads sem multipart)."""
        ...

    def enviar(
        self,
        origem: Path,
        chave: str,
        tipo: str,
        codificacao: str | None = None,
        cache: str | None = None,
    ) -> None: ...

    def apagar(self, chave: str) -> None: ...


@dataclass(frozen=True)
class ResumoPublicacao:
    enviados: int
    apagados: int
    inalterados: int = 0


def _resumo(caminho: Path, algoritmo: str) -> str:
    resumo = hashlib.new(algoritmo)
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1 << 20), b""):
            resumo.update(bloco)
    return resumo.hexdigest()


def _sha256(caminho: Path) -> str:
    return _resumo(caminho, "sha256")


def _md5(caminho: Path) -> str:
    return _resumo(caminho, "md5")


def _linhas(caminho: Path) -> int | None:
    if caminho.suffix != ".parquet":
        return None
    import pyarrow.parquet as pq

    return pq.ParquetFile(caminho).metadata.num_rows


def arquivos_publicos(publico: Path) -> dict[str, Path]:
    arquivos = {
        caminho.relative_to(publico).as_posix(): caminho
        for caminho in publico.rglob("*")
        if caminho.is_file()
    }
    proibidos = sorted(chave for chave in arquivos if not chave.startswith(PERMITIDOS))
    if proibidos:
        raise ErroPublicacao(f"fora de {', '.join(PERMITIDOS)}: {', '.join(proibidos)}")
    if not any(chave.startswith("marts/") for chave in arquivos):
        raise ErroPublicacao(f"nenhum mart em {publico}/marts")
    return arquivos


def montar_manifesto(
    arquivos: Mapping[str, Path], gerado_em: datetime, versao: str
) -> dict[str, Any]:
    """Lista os dados para download (marts e linhagem); os arquivos do site ficam de fora."""
    return {
        "gerado_em": gerado_em.isoformat(),
        "versao": versao,
        "arquivos": [
            {
                "caminho": chave,
                "bytes": caminho.stat().st_size,
                "linhas": _linhas(caminho),
                "sha256": _sha256(caminho),
            }
            for chave, caminho in sorted(arquivos.items())
            if not chave.startswith(SITE)
        ],
    }


def publicar(
    publicador: Publicador, publico: Path, gerado_em: datetime, versao: str
) -> ResumoPublicacao:
    """Envia o que mudou, depois o manifesto, e só então apaga o que deixou de existir.

    Só envia o arquivo cujo MD5 difere do ETag no bucket. Sem `site/` local (o `coletor site`
    falhou ou não rodou), o `site/` do bucket fica como está, com os dados anteriores.
    """
    arquivos = arquivos_publicos(publico)
    anteriores = publicador.listar()
    enviados = 0
    for chave, caminho in sorted(arquivos.items()):
        if anteriores.get(chave) == _md5(caminho):
            continue
        tipo = TIPOS.get(caminho.suffix, "application/octet-stream")
        if chave.startswith(SITE):
            publicador.enviar(caminho, chave, tipo, codificacao="gzip", cache=CACHE_SITE)
        else:
            publicador.enviar(caminho, chave, tipo)
        enviados += 1
    manifesto = montar_manifesto(arquivos, gerado_em, versao)
    with tempfile.TemporaryDirectory() as pasta:
        destino = Path(pasta) / MANIFESTO
        destino.write_text(json.dumps(manifesto, ensure_ascii=False, indent=1), encoding="utf-8")
        publicador.enviar(destino, MANIFESTO, TIPOS[".json"])
    tem_site = any(chave.startswith(SITE) for chave in arquivos)
    sobrando = sorted(
        chave
        for chave in set(anteriores) - set(arquivos) - {MANIFESTO}
        if tem_site or not chave.startswith(SITE)
    )
    for chave in sobrando:
        publicador.apagar(chave)
    inalterados = len(arquivos) - enviados
    log.info(
        "publicados %d arquivo(s) (%d sem mudança); %d removido(s)",
        enviados,
        inalterados,
        len(sobrando),
    )
    return ResumoPublicacao(enviados + 1, len(sobrando), inalterados)


class R2Publicador:
    def __init__(self, conta: str, chave_id: str, segredo: str, bucket: str) -> None:
        import boto3
        from boto3.s3.transfer import TransferConfig

        self._bucket = bucket
        self._s3 = boto3.client(
            "s3",
            endpoint_url=f"https://{conta}.r2.cloudflarestorage.com",
            aws_access_key_id=chave_id,
            aws_secret_access_key=segredo,
            region_name="auto",
        )
        # upload sem multipart (até 4 GB): o ETag fica sendo o MD5, que o envio incremental compara
        self._transferencia = TransferConfig(multipart_threshold=4 * 1024**3)

    def listar(self) -> dict[str, str]:
        chaves: dict[str, str] = {}
        for pagina in self._s3.get_paginator("list_objects_v2").paginate(Bucket=self._bucket):
            for objeto in pagina.get("Contents", []):
                chaves[objeto["Key"]] = objeto["ETag"].strip('"')
        return chaves

    def enviar(
        self,
        origem: Path,
        chave: str,
        tipo: str,
        codificacao: str | None = None,
        cache: str | None = None,
    ) -> None:
        extras = {"ContentType": tipo}
        if codificacao:
            extras["ContentEncoding"] = codificacao
        if cache:
            extras["CacheControl"] = cache
        self._s3.upload_file(
            str(origem), self._bucket, chave, ExtraArgs=extras, Config=self._transferencia
        )

    def apagar(self, chave: str) -> None:
        self._s3.delete_object(Bucket=self._bucket, Key=chave)
```

- [ ] **Step 4: Veja passar**

Run: `uv run pytest tests/test_publicacao.py -q`
Expected: PASS (9 testes).

- [ ] **Step 5: Prova de mutação**

Em `publicar`, apague as duas linhas
`if anteriores.get(chave) == _md5(caminho):` / `continue`. Run:
`uv run pytest tests/test_publicacao.py -q -k so_envia`.
Expected: FAIL (todos os arquivos são reenviados). Desfaça e confirme o PASS.

- [ ] **Step 6: Lint, suíte e commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest -q
git add coletor/publicacao.py tests/test_publicacao.py
git commit -m "feat(coletor): publicar só o que mudou e o site em gzip"
```

---

### Task 8: CI, pipeline e documentação

**Files:**
- Modify: `.github/workflows/ci.yml`, `.github/workflows/pipeline.yml`
- Modify: `docs/modelos-de-dados.md`, `AGENTS.md`, `docs/roteiro.md`, `README.md`

**Interfaces:**
- Consumes: `coletor site` (tarefa 6) e `coletor publicar` (tarefa 7).

- [ ] **Step 1: CI**

Em `.github/workflows/ci.yml`, no passo `dbt sobre o lago vazio`, troque o bloco `run:` por:

```yaml
        run: |
          uv run python scripts/lago_vazio.py
          mkdir -p "$ELEITORADO_PUBLICO/marts"
          uv run dbt seed --project-dir dbt --profiles-dir dbt --target ci
          uv run dbt run --project-dir dbt --profiles-dir dbt --target ci
          uv run dbt test --project-dir dbt --profiles-dir dbt --target ci
          # os arquivos do site saem válidos mesmo sem dado nenhum
          uv run coletor --target ci site
```

- [ ] **Step 2: Pipeline**

Em `.github/workflows/pipeline.yml`, no passo `publicar`, troque `run: uv run coletor publicar`
por:

```yaml
        # o site não impede a publicação dos marts: sem site/ local, o do bucket fica como está
        run: |
          site=0
          uv run coletor site || site=$?
          uv run coletor publicar
          if [ "$site" -ne 0 ]; then
            echo "::error::coletor site falhou: o site público ficou com os dados anteriores"
            exit 1
          fi
```

(o `if:` e o `env:` do passo continuam iguais).

- [ ] **Step 3: Documentação**

Em `docs/modelos-de-dados.md`, antes de `## Camada intermediate`, acrescente:

```markdown
## Arquivos do site (`site/`)

O site público lê arquivos JSON pequenos, gerados todo dia a partir dos marts pelos modelos
`site_*` (pasta `dbt/models/site/`, que só lê marts e seeds) e gravados pelo `coletor site`.
Ficam no R2 em `site/`, em gzip (`Content-Encoding: gzip`), fora do `manifesto.json`.

| Caminho | Conteúdo |
|---|---|
| `site/resumo.json` | Números da capa, tipos de alerta (texto do seed `site_alerta_tipos`), alertas recentes, situação das fontes |
| `site/busca/parlamentares.json` | Todos os parlamentares |
| `site/busca/empresas/<abc>.json` | Empresas com uma palavra da razão social começando por `<abc>` (blocos grandes subdivididos em 4 letras) |
| `site/parlamentar/<casa>-<id>.json` | Cota, emendas e alertas de um parlamentar |
| `site/empresa/<abc>.json` | Empresas cuja raiz do CNPJ começa por `<abc>`: cadastro, o que recebeu, sanções e alertas |
| `site/alertas/<tipo>/<n>.json` | Alertas de um tipo, 500 por página |

O formato de cada arquivo está nos JSON Schemas de `site/esquemas/`; há exemplos em
`site/exemplos/`. Desenho em `docs/superpowers/specs/2026-10-07-site-publico-design.md`.
```

Em `AGENTS.md`:
- Em "O projeto", depois do item de `dbt/`, acrescente:

```markdown
- `site/`: contrato dos dados do site público (`site/esquemas/`, JSON Schemas; `site/exemplos/`)
  e, depois do plano 11, o frontend. Os modelos `dbt/models/site/` montam os arquivos e o
  `coletor site` os grava em `publico/site/`, que o `coletor publicar` envia ao R2.
```

- Em "Convenções", acrescente:

```markdown
- Mudança no formato de um arquivo do site: altere no mesmo PR o modelo `site_*`, o esquema em
  `site/esquemas/` e os exemplos em `site/exemplos/` (e o frontend, se ele usa o campo).
```

- Em "Operação: o que já se sabe", acrescente:

```markdown
- **Site:** o `coletor site` roda no passo de publicação do pipeline. Se ele falhar, os marts
  são publicados mesmo assim e o `site/` do R2 fica com os dados da véspera. O `publicar` só
  envia o que mudou (MD5 × ETag), então o site não reenvia milhares de arquivos por dia.
```

Em `docs/roteiro.md`, no item 8 (Produto público), troque o parágrafo por:

```markdown
Spec em `docs/superpowers/specs/2026-10-07-site-publico-design.md`. Plano 10 (dados do site:
modelos `site_*`, `coletor site`, publicação incremental) em
`docs/superpowers/plans/2026-10-07-plano-10-dados-do-site.md`; plano 11 (frontend em `site/`,
Cloudflare Pages) a seguir. **Usuário:** criar o projeto no Cloudflare Pages e a regra de CORS
do bucket R2 (spec, seção 9).
```

Em `README.md`, no item **Público** (por volta da linha 104), acrescente ao fim do parágrafo:
`` Os arquivos do site público ficam em `site/` (ver `docs/modelos-de-dados.md`). ``

- [ ] **Step 4: Verificação completa**

Run (PowerShell):

```powershell
uv run ruff check .; uv run ruff format --check .; uv run pytest -q
$env:ELEITORADO_LAGO = "dbt/tests/lago_vazio"; $env:ELEITORADO_PUBLICO = "$env:TEMP\publico-ci"
uv run python scripts/lago_vazio.py
uv run dbt seed --project-dir dbt --profiles-dir dbt --target ci
uv run dbt run --project-dir dbt --profiles-dir dbt --target ci
uv run dbt test --project-dir dbt --profiles-dir dbt --target ci
uv run coletor --target ci site
```

Expected: ruff limpo; pytest todo verde; dbt sem erro (os 8 testes unitários `site_*` em PASS);
`coletor site` com 2 arquivos.

- [ ] **Step 5: Commit, push e PR**

```bash
git add .github/workflows docs AGENTS.md README.md
git commit -m "ci: seeds e coletor site no CI; site no passo de publicação; docs do site"
git push -u origin feat/site-dados
gh pr create --base main --title "Site público: dados (plano 10)" --body "Plano 10 da spec do site público (docs/superpowers/specs/2026-10-07-site-publico-design.md): contrato (site/esquemas, site/exemplos), modelos dbt site_*, coletor site (valida e grava em gzip) e publicar incremental com o site em site/ no R2. Plano: docs/superpowers/plans/2026-10-07-plano-10-dados-do-site.md."
```

Expected: PR aberto e o check `testes` verde. O merge é do usuário.

## Depois do merge (usuário)

- Na próxima execução do pipeline, conferir no log: `site: N arquivo(s)` (~14 mil) e o tempo do
  `publicar` (a primeira vez envia tudo; nas seguintes, só o que mudou).
- Conferir `https://pub-e140b10136c94c9eb7cdb0a31fe603f3.r2.dev/site/resumo.json` (deve abrir
  descomprimido no navegador).
