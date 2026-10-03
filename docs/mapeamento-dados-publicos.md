# Mapeamento de fontes oficiais brasileiras de dados públicos

Data de referência: **03/10/2026**. Finalidade: **integração em sistema ou pipeline de coleta**.

21 instituições, incluindo o MGI; CGU consolidada; Câmara e Senado separados. Principais bases, sem pretensão de inventariar todos os recursos existentes em cada portal.

Pesquisa de documentação e recursos oficiais. Algumas respostas públicas de serviço foram inspecionadas; nenhuma cobertura de testes autenticados ou SLA foi realizada. Uma falha na ferramenta de obtenção não prova indisponibilidade do serviço.

## Como ler o catálogo

- **conteudo**: Retorna registros ou valores da base.
- **catalogo**: Retorna descrição do conjunto, metadados e URLs de recursos; não implica consulta de registros.
- **geoespacial_conteudo**: WFS ou outro serviço de feições; WMS de visualização não substitui vetores/microdados.
- **restrita**: Exige habilitação institucional ou credenciais vinculadas a uma entidade; não tratar como dado aberto anônimo.
- **contratacao**: Produto oficial sujeito a contratação; não tratar como API pública gratuita.

Granularidades resumem o acervo; chaves_sugeridas são propostas de integração, não contratos universais de nomes de colunas nem autorização de cruzamento de registros pessoais.

## Visão institucional

| Órgão / portal oficial | Principais bases | Obtenção prioritária |
|---|---|---|
| [Banco Central do Brasil (BCB)](https://dadosabertos.bcb.gov.br/) | SGS: Selic, crédito, inflação, atividade e outras séries econômicas; PTAX: taxas de câmbio; Expectativas de Mercado / Focus; IFData: dados selecionados de instituições financeiras | APIs de conteúdo REST (SGS) e OData (Olinda). |
| [Receita Federal do Brasil (RFB)](https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/dados-abertos) | CNPJ: empresas, estabelecimentos, sócios, Simples/MEI e tabelas auxiliares; Cadastros CNO e CAFIR; Arrecadação e benefícios/renúncias fiscais; Grandes Números do IRPF e distribuição de renda | Para uma base aberta local de CNPJ: arquivos em lote. APIs oficiais de consulta individual exigem habilitação governamental ou contratação. |
| [Comissão de Valores Mobiliários (CVM)](https://dados.cvm.gov.br/) | Companhias abertas: cadastro, DFP, ITR, FRE e documentos periódicos/eventuais; Fundos de investimento: cadastro, Informe Diário e composição de carteiras (CDA); Fundos estruturados: informes FII/FIP e outros conjuntos publicados; Ofertas públicas e processos sancionadores | API CKAN para descobrir conjuntos e recursos; baixar os arquivos CSV/ZIP para consumir os registros. |
| [Secretaria do Tesouro Nacional (STN)](https://www.tesourotransparente.gov.br/ckan/) | Siconfi: DCA, RREO, RGF e Matriz de Saldos Contábeis (MSC); Entes da Federação e extrato de entregas; Transferências constitucionais e legais: FPM, FPE, Fundeb e outras modalidades; Tesouro Direto, dívida pública e Resultado do Tesouro Nacional | APIs Siconfi e de transferências para conjuntos cobertos; catálogo e arquivos para demais séries. |
| [Controladoria-Geral da União (CGU)](https://portaldatransparencia.gov.br/) | Despesas, receitas, contratos, licitações e transferências do Executivo federal; Emendas parlamentares; Servidores, viagens e cartões de pagamento; Benefícios sociais publicados no Portal; Sanções: CEIS, CNEP, CEPIM e CEAF | API REST para consultas filtradas; downloads para carga completa e grandes volumes. |
| [Ministério da Gestão e da Inovação em Serviços Públicos (MGI)](https://www.gov.br/gestao/pt-br) | Compras.gov.br: licitações, contratações, itens, resultados e compras sem licitação; Compras.gov.br: CATMAT, CATSER, fornecedores, pesquisa de preços e planejamento PGC; Compras.gov.br: contratos, itens de contratos e atas de registro de preços; PNCP: contratações, contratos, atas e planos anuais de contratação publicados pelos entes; Transferegov: Transferências Especiais e Gestão de Parcerias; Transferegov: Transferências Fundo a Fundo e Termos de Execução Descentralizada (TED); Transferegov: Transferências Discricionárias e Legais — programas, propostas e instrumentos; SIORG: órgãos, entidades, unidades, hierarquia, histórico e cargos/funções; PEP / Observatório de Pessoal: quantitativos, perfil, despesas, ingressos e saídas; Gestão de Pessoas: bases abertas de afastamentos/licenças e gratificações; SPU: imóveis da União, utilizações, responsáveis e localização geocodificada | APIs oficiais de Compras.gov.br, PNCP, módulos públicos do Transferegov e SIORG; CSV e exportações de painéis para demais bases. |
| [Tribunal de Contas da União (TCU)](https://sites.tcu.gov.br/dados-abertos/) | Acórdãos e jurisprudência; Termos contratuais e aditivos do próprio TCU; Responsáveis inabilitados e licitantes inidôneos; Contas julgadas irregulares e responsáveis para fins eleitorais | Webservices públicos para decisões, contratos do TCU e listas de responsáveis. |
| [Instituto Brasileiro de Geografia e Estatística (IBGE)](https://servicodados.ibge.gov.br/api/docs/) | SIDRA / agregados de pesquisas e censos: população, PIB, preços, trabalho e outros indicadores; Localidades e códigos territoriais; Microdados PNAD Contínua e Censo Demográfico; Malhas geográficas | APIs de agregados/localidades para consultas; repositórios de arquivos para microdados e geografia. |
| [Instituto de Pesquisa Econômica Aplicada (IPEA)](https://www.ipeadata.gov.br/) | Ipeadata Macroeconômico; Ipeadata Regional; Ipeadata Social | API REST/OData v4 do Ipeadata. |
| [Ministério da Saúde / DATASUS](https://dadosabertos.saude.gov.br/) | CNES: estabelecimentos de saúde; SIM: mortalidade; SINASC: nascidos vivos; SRAG / SIVEP-Gripe; PNI: doses de vacinação; SIA/SIH: produção ambulatorial e internações | API de conteúdo do Ministério da Saúde para bases cobertas; arquivos DATASUS para séries históricas e conjuntos não cobertos. |
| [Agência Nacional de Vigilância Sanitária (ANVISA)](https://www.gov.br/anvisa/pt-br/acessoainformacao/dadosabertos) | Medicamentos registrados; Produtos para saúde e modelos; VigiMed e notificações de vigilância; SNGPC: vendas de medicamentos controlados; CMED: preços máximos de medicamentos | Downloads HTTP de arquivos e dicionários; API pública de conteúdo com contrato estável dessas bases não confirmada. |
| [Agência Nacional de Saúde Suplementar (ANS)](https://www.gov.br/ans/pt-br/acesso-a-informacao/perfil-do-setor/dados-abertos-1) | Operadoras ativas / CADOP; Beneficiários por operadora / SIB; Demonstrações contábeis / DIOPS; Produtos e prestadores hospitalares; Demandas/reclamações de consumidores | Downloads HTTP públicos de arquivos; endpoint público atual da API de operadoras não confirmado. |
| [Instituto Nacional de Estudos e Pesquisas Educacionais Anísio Teixeira (INEP)](https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/microdados-1) | Censo Escolar; Censo da Educação Superior; Enem; Saeb | Downloads de microdados por edição; API pública de conteúdo dessas quatro bases não confirmada nesta pesquisa. |
| [Coordenação de Aperfeiçoamento de Pessoal de Nível Superior (CAPES)](https://dadosabertos.capes.gov.br/dataset/) | Programas de pós-graduação stricto sensu; Docentes e discentes; Produção intelectual; Concessão de bolsas a instituições de ensino superior | CKAN DataStore nos recursos habilitados; downloads para demais recursos. |
| [Ministério do Trabalho e Emprego (MTE)](https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/estatisticas-trabalho/microdados-rais-e-caged) | RAIS Trabalhador/Vínculos; RAIS Estabelecimentos; CAGED Estatístico histórico; Novo Caged: admissões, desligamentos e saldo de empregos | Microdados não identificados por FTP/arquivos; API REST pública dessas bases não confirmada. |
| [Instituto Nacional do Seguro Social (INSS)](https://dadosabertos.inss.gov.br/) | Benefícios concedidos; Benefícios emitidos e mantidos; Dados agregados da folha de pagamento; Requerimentos administrativos solicitados e pendentes | Downloads de recursos recentes do catálogo institucional; API pública de catálogo/linhas não confirmada. |
| [Instituto Nacional de Pesquisas Espaciais (INPE)](https://terrabrasilis.dpi.inpe.br/) | PRODES: desmatamento; DETER: alertas de desmatamento; Queimadas: focos de fogo ativo; Área queimada, eventos de fogo e risco de fogo | WFS para feições vetoriais publicadas; downloads de arquivos geoespaciais e tabelas conforme produto. |
| [Ministério da Justiça e Segurança Pública (MJSP / SINESP)](https://www.gov.br/mj/pt-br/acesso-a-informacao/dados-abertos) | Dados Nacionais de Segurança Pública / SINESP VDE; Pesquisa Perfil das Instituições de Segurança Pública | Downloads de bases e notas metodológicas; API pública de conteúdo VDE/Perfil não confirmada. |
| [Câmara dos Deputados](https://dadosabertos.camara.leg.br/) | Deputados e histórico parlamentar; Proposições e tramitações; Votações e votos individuais; Despesas da Cota para o Exercício da Atividade Parlamentar (CEAP) | API REST v2 para consultas; arquivos históricos por conjunto/ano/legislatura. |
| [Senado Federal](https://www12.senado.leg.br/dados-abertos) | Senadores, mandatos e filiações; Matérias legislativas e tramitações; Votações nominais; CEAPS: cota parlamentar; Contratos e licitações administrativas | API legislativa e API administrativa separadas; arquivos conforme conjunto. |
| [Conselho Nacional de Justiça (CNJ)](https://www.cnj.jus.br/sistemas/datajud/api-publica/) | DataJud: processos, classes, assuntos, órgãos julgadores e movimentos; Justiça em Números / SIESPJ: indicadores e séries estatísticas | API DataJud por tribunal; arquivos estatísticos publicados pelo CNJ para Justiça em Números. |

## Fichas de integração

### Banco Central do Brasil (BCB)

Portal: [fonte oficial](https://dadosabertos.bcb.gov.br/).

**Bases prioritárias**

- SGS: Selic, crédito, inflação, atividade e outras séries econômicas
- PTAX: taxas de câmbio
- Expectativas de Mercado / Focus
- IFData: dados selecionados de instituições financeiras

**Obtenção:** APIs de conteúdo REST (SGS) e OData (Olinda).

**Granularidade:** Série/data; moeda/boletim; instituição financeira/data-base, conforme o recurso.

**Atualização:** Por série; SGS possui séries diárias e mensais. IFData é trimestral, com defasagem de publicação de 60 ou 90 dias conforme a data-base.

**Interfaces e autenticação**

- **SGS** — tipo: conteudo; método: GET.
  - URL/base: `https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados`.
  - [Documentação oficial](https://dadosabertos.bcb.gov.br/dataset/11-taxa-de-juros---selic).
  - Autenticação: Consulta pública sem chave.
  - Recursos/paginação: formato=json ou csv; dataInicial e dataFinal. Séries diárias exigem filtros e janelas de até 10 anos.
  - Verificação: `documentada`.
- **PTAX** — tipo: conteudo; método: GET.
  - URL/base: `https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/`.
  - [Documentação oficial](https://www.bcb.gov.br/conteudo/dadosabertos/BCBDepin/gnastportal-dados-abertostaxas-de-cambio---todos-os-boletins-diarios.pdf).
  - Autenticação: Consulta pública sem chave.
  - Recursos/paginação: Recursos de cotação por data/período e moedas; filtros e paginação OData.
  - Verificação: `documentada`.
- **Expectativas de Mercado** — tipo: conteudo; método: GET.
  - URL/base: `https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/`.
  - [Documentação oficial](https://dadosabertos.bcb.gov.br/dataset/expectativas-mercado).
  - Autenticação: Consulta pública sem chave.
  - Verificação: `documentada`.
- **IFData** — tipo: conteudo; método: GET.
  - URL/base: `https://olinda.bcb.gov.br/olinda/servico/IFDATA/versao/v1/odata/`.
  - [Documentação oficial](https://dadosabertos.bcb.gov.br/dataset/ifdata---dados-selecionados-de-instituies-financeiras).
  - Autenticação: Consulta pública sem chave.
  - Verificação: `documentada`.

**Arquivos e formatos**

- [Repositório/recurso](https://dadosabertos.bcb.gov.br/) — CSV, JSON. Formatos e recursos variam por conjunto; várias exportações são fornecidas pelas próprias APIs.

**Chaves sugeridas:** código de série SGS; data de referência; moeda; identificador da instituição.

**Observações de integração**

- Preservar código, unidade e periodicidade de cada série.
- O limite de 10 anos refere-se às consultas JSON/CSV de séries históricas diárias; não aplicar esse limite indiscriminadamente a toda API do BCB.

**Fontes da ficha**

- [Fonte oficial 1](https://dadosabertos.bcb.gov.br/dataset/11-taxa-de-juros---selic)
- [Fonte oficial 2](https://dadosabertos.bcb.gov.br/dataset/expectativas-mercado)
- [Fonte oficial 3](https://dadosabertos.bcb.gov.br/dataset/ifdata---dados-selecionados-de-instituies-financeiras)

### Receita Federal do Brasil (RFB)

Portal: [fonte oficial](https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/dados-abertos).

**Bases prioritárias**

- CNPJ: empresas, estabelecimentos, sócios, Simples/MEI e tabelas auxiliares
- Cadastros CNO e CAFIR
- Arrecadação e benefícios/renúncias fiscais
- Grandes Números do IRPF e distribuição de renda

**Obtenção:** Para uma base aberta local de CNPJ: arquivos em lote. APIs oficiais de consulta individual exigem habilitação governamental ou contratação.

**Granularidade:** Empresa, estabelecimento e sócio no CNPJ; agregados e cadastros conforme o conjunto.

**Atualização:** CNPJ publicado por competências; verificar competência efetivamente disponível em cada recurso. Outras bases possuem calendários próprios.

**Interfaces e autenticação**

- **Consulta CNPJ via Conecta gov.br** — tipo: restrita; método: GET.
  - URL/base: `https://apigateway.conectagov.estaleiro.serpro.gov.br/api-cnpj-basica/v2/basica/`.
  - [Documentação oficial](https://www.gov.br/conecta/catalogo/apis/consulta-cnpj).
  - Autenticação: Adesão de órgão público elegível, chaves de acesso e cadastro de IP conforme Conecta; não é uma API pública anônima.
  - Verificação: `documentada`.
- **Consulta CNPJ Serpro** — tipo: contratacao; método: Consultar documentação do produto contratado..
  - URL/base: não registrada como contrato confirmado.
  - [Documentação oficial](https://loja.serpro.gov.br/es/pin/biblioteca/index.html).
  - Autenticação: Contratação e credenciais do produto.
  - Verificação: `produto_oficial_documentado`.

**Arquivos e formatos**

- [Repositório/recurso](https://dados.gov.br/dados/conjuntos-dados/cadastro-nacional-da-pessoa-juridica---cnpj) — CSV, ZIP. Página oficial atual de descoberta do CNPJ; obter os links de recursos publicados, sem depender de um diretório histórico fixo.
- [Repositório/recurso](https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/dados) — CSV, JSON, XML, ODS. Repositório de arquivos da RFB; disponibilidade e formato por conjunto.

**Chaves sugeridas:** CNPJ como texto; CNPJ básico e estabelecimento conforme layout; competência do arquivo; CNAE; códigos territoriais com tabela de correspondência.

**Observações de integração**

- Nenhuma API pública anônima de consulta individual ao CNPJ foi confirmada nesta pesquisa.
- APIs de terceiros não substituem a fonte oficial e podem ter defasagens próprias.
- CPF de sócio mascarado não é identificador seguro para vinculação individual.
- Manter identificadores CNPJ como texto e respeitar o dicionário/layout publicado.

**Fontes da ficha**

- [Fonte oficial 1](https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/dados-abertos)
- [Fonte oficial 2](https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/dados-abertos/cadastros)
- [Fonte oficial 3](https://www.gov.br/conecta/catalogo/apis/consulta-cnpj)
- [Fonte oficial 4](https://loja.serpro.gov.br/es/pin/biblioteca/index.html)

### Comissão de Valores Mobiliários (CVM)

Portal: [fonte oficial](https://dados.cvm.gov.br/).

**Bases prioritárias**

- Companhias abertas: cadastro, DFP, ITR, FRE e documentos periódicos/eventuais
- Fundos de investimento: cadastro, Informe Diário e composição de carteiras (CDA)
- Fundos estruturados: informes FII/FIP e outros conjuntos publicados
- Ofertas públicas e processos sancionadores

**Obtenção:** API CKAN para descobrir conjuntos e recursos; baixar os arquivos CSV/ZIP para consumir os registros.

**Granularidade:** Regulado/fundo/companhia, documento, conta financeira e competência, conforme a base.

**Atualização:** DFP: semanal, com reapresentações. Informe Diário: meses corrente e anterior atualizados diariamente; demais meses da janela recente, semanalmente.

**Interfaces e autenticação**

- **CKAN Action API** — tipo: catalogo; método: GET.
  - URL/base: `https://dados.cvm.gov.br/api/3/action/`.
  - [Documentação oficial](https://dados.cvm.gov.br/api/3/action/help_show?name=package_show).
  - Autenticação: Leitura pública sem chave.
  - Recursos/paginação: package_search e package_show; exemplo package_show?id=fi-doc-inf_diario.
  - Verificação: `resposta_json_verificada`.

**Arquivos e formatos**

- [Repositório/recurso](https://dados.cvm.gov.br/dados/) — CSV, ZIP, TXT. Repositório de arquivos; dicionários de dados disponíveis nos conjuntos.
- [Repositório/recurso](https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/) — CSV, ZIP. Histórico de DFP desde 2010 conforme a página do conjunto.

**Chaves sugeridas:** CNPJ; código CVM; data de competência; versão do documento; código de conta.

**Observações de integração**

- A API de catálogo não equivale a uma API de consultas financeiras por linha.
- Guardar competência e versão do documento; reapresentações podem alterar dados já coletados.
- Não tratar planos futuros de abertura como bases disponíveis hoje.

**Fontes da ficha**

- [Fonte oficial 1](https://dados.cvm.gov.br/)
- [Fonte oficial 2](https://dados.cvm.gov.br/dataset/cia_aberta-doc-dfp)
- [Fonte oficial 3](https://dados.cvm.gov.br/dataset/fi-doc-inf_diario)
- [Fonte oficial 4](https://dados.cvm.gov.br/api/3/action/package_show?id=fi-doc-inf_diario)

### Secretaria do Tesouro Nacional (STN)

Portal: [fonte oficial](https://www.tesourotransparente.gov.br/ckan/).

**Bases prioritárias**

- Siconfi: DCA, RREO, RGF e Matriz de Saldos Contábeis (MSC)
- Entes da Federação e extrato de entregas
- Transferências constitucionais e legais: FPM, FPE, Fundeb e outras modalidades
- Tesouro Direto, dívida pública e Resultado do Tesouro Nacional

**Obtenção:** APIs Siconfi e de transferências para conjuntos cobertos; catálogo e arquivos para demais séries.

**Granularidade:** Ente/exercício/período/anexo/conta para demonstrativos; ente/transferência/mês/decêndio para repasses.

**Atualização:** Por demonstrativo e competência: anual, bimestral, quadrimestral/semestral ou mensal conforme a base; transferências podem ter agregação mensal/decendial.

**Interfaces e autenticação**

- **Siconfi** — tipo: conteudo; método: GET.
  - URL/base: `https://apidatalake.tesouro.gov.br/ords/siconfi/tt/`.
  - [Documentação oficial](https://apidatalake.tesouro.gov.br/docs/siconfi/).
  - Autenticação: Sem identificação ou remuneração para consulta pública.
  - Recursos/paginação: Consultar recursos, filtros e paginação na documentação; padrão institucional publicado de 5.000 itens por página.
  - Verificação: `documentacao_institucional_verificada_endpoint_nao_testado`.
- **Transferências constitucionais** — tipo: conteudo; método: GET.
  - URL/base: `https://apiapex.tesouro.gov.br/aria/v1/transferencias_constitucionais/custom/`.
  - [Documentação oficial](https://www.tesourotransparente.gov.br/ckan/dataset/api-de-transferencias-constitucionais).
  - Autenticação: Rotas de consulta marcadas como públicas na documentação do Tesouro; confirmar exigências na rota escolhida.
  - Recursos/paginação: transferencias, estados, municipios, por_estados, por_estados_detalhe, por_estado_municipio e por_estado_municipio_detalhe.
  - Verificação: `documentada`.

**Arquivos e formatos**

- [Repositório/recurso](https://www.tesourotransparente.gov.br/ckan/dataset) — CSV, XLSX, ZIP, GZ. Disponibilidade por conjunto. Siconfi possui recursos específicos de API; não pressupor CSV em todas as bases.

**Chaves sugeridas:** código IBGE do ente; exercício; período; anexo; conta; coluna e consolidação.

**Observações de integração**

- Tratar retificações e extrato de entregas na coleta.
- Não somar níveis de conta ou colunas contábeis sem verificar anexo, consolidação e regime.
- STN possui várias famílias de APIs; uma URL não cobre todo o Tesouro Transparente.

**Fontes da ficha**

- [Fonte oficial 1](https://www.tesourotransparente.gov.br/consultas/consultas-siconfi/siconfi-api-de-dados-abertos)
- [Fonte oficial 2](https://www.tesourotransparente.gov.br/ckan/dataset/api-de-transferencias-constitucionais)
- [Fonte oficial 3](https://sisweb.tesouro.gov.br/apex/f?p=10250:7:0::NO:7:P7_ID_PROJETO:1586)

### Controladoria-Geral da União (CGU)

Portal: [fonte oficial](https://portaldatransparencia.gov.br/).

**Bases prioritárias**

- Despesas, receitas, contratos, licitações e transferências do Executivo federal
- Emendas parlamentares
- Servidores, viagens e cartões de pagamento
- Benefícios sociais publicados no Portal
- Sanções: CEIS, CNEP, CEPIM e CEAF

**Obtenção:** API REST para consultas filtradas; downloads para carga completa e grandes volumes.

**Granularidade:** Documento, contrato, licitação, sanção, beneficiário ou agregado territorial, conforme endpoint.

**Atualização:** Varia por base e sistema de origem; verificar página de origem/atualização e competência publicada.

**Interfaces e autenticação**

- **API do Portal da Transparência** — tipo: conteudo; método: GET.
  - URL/base: `https://api.portaldatransparencia.gov.br/api-de-dados/`.
  - [Documentação oficial](https://api.portaldatransparencia.gov.br/swagger-ui/index.html).
  - Autenticação: Token obtido pelo cadastro indicado no Portal; header chave-api-dados.
  - Recursos/paginação: Recursos, filtros e parâmetro pagina conforme endpoint. A página oficial consultada informa 400 requisições/minuto de 06:00 a 23:59 e 700 de 00:00 a 05:59.
  - Verificação: `documentada_autenticacao_nao_testada`.

**Arquivos e formatos**

- [Repositório/recurso](https://portaldatransparencia.gov.br/download-de-dados) — CSV, ZIP. O Portal recomenda planilhas/download para o conjunto completo; periodicidade por base.

**Chaves sugeridas:** identificador do documento/contrato/sanção; CNPJ; código IBGE; código SIAFI; competência.

**Observações de integração**

- O Portal não reúne todas as despesas de todos os poderes, estados e municípios.
- API e arquivos podem ter escopos e granularidades diferentes; verificar cobertura em cada recurso.
- Limites de requisição são configuração mutável: confirmar antes de produção.

**Fontes da ficha**

- [Fonte oficial 1](https://portaldatransparencia.gov.br/api-de-dados)
- [Fonte oficial 2](https://portaldatransparencia.gov.br/pagina-interna/603579-api-de-dados-exemplos-de-uso)
- [Fonte oficial 3](https://portaldatransparencia.gov.br/download-de-dados)

### Ministério da Gestão e da Inovação em Serviços Públicos (MGI)

Portal: [fonte oficial](https://www.gov.br/gestao/pt-br).

**Bases prioritárias**

- Compras.gov.br: licitações, contratações, itens, resultados e compras sem licitação
- Compras.gov.br: CATMAT, CATSER, fornecedores, pesquisa de preços e planejamento PGC
- Compras.gov.br: contratos, itens de contratos e atas de registro de preços
- PNCP: contratações, contratos, atas e planos anuais de contratação publicados pelos entes
- Transferegov: Transferências Especiais e Gestão de Parcerias
- Transferegov: Transferências Fundo a Fundo e Termos de Execução Descentralizada (TED)
- Transferegov: Transferências Discricionárias e Legais — programas, propostas e instrumentos
- SIORG: órgãos, entidades, unidades, hierarquia, histórico e cargos/funções
- PEP / Observatório de Pessoal: quantitativos, perfil, despesas, ingressos e saídas
- Gestão de Pessoas: bases abertas de afastamentos/licenças e gratificações
- SPU: imóveis da União, utilizações, responsáveis e localização geocodificada

**Obtenção:** APIs oficiais de Compras.gov.br, PNCP, módulos públicos do Transferegov e SIORG; CSV e exportações de painéis para demais bases.

**Granularidade:** Compra/item/resultado/contrato/ata e fornecedor; plano de contratação; programa/proposta/instrumento/transferência e execução; unidade e hierarquia SIORG; estatística de pessoal por competência/dimensão; ocorrência/gratificação conforme layout; imóvel e utilização patrimonial.

**Atualização:** Por família: arquivos Compras.gov.br com cortes diários/mensais/anuais; PNCP depende das publicações e retificações dos entes; frequência uniforme do Transferegov não confirmada; SIORG oferece consulta à estrutura vigente, sem SLA confirmado; PEP mensal; Afastamentos/Licenças mensal segundo inventário; SPU exibe referência março/2026 e aviso de migração.

**Interfaces e autenticação**

- **Dados Abertos Compras.gov.br** — tipo: conteudo; método: GET.
  - URL/base: `https://dadosabertos.compras.gov.br/`.
  - [Documentação oficial](https://www.gov.br/compras/pt-br/acesso-a-informacao/manuais/manual-dados-abertos/manual-api-compras.pdf).
  - Autenticação: Os exemplos de consultas GET do manual não usam chave/token; chamadas de conteúdo não testadas nesta pesquisa.
  - Recursos/paginação: Manual versão 2.0, fevereiro/2026. Exemplos: /modulo-contratacoes/1_consultarContratacoes_PNCP_14133; /modulo-contratacoes/2_consultarItensContratacoes_PNCP_14133; /modulo-contratos/1_consultarContratos; /modulo-fornecedor/1_consultarFornecedor. Filtros, pagina e tamanhoPagina conforme cada recurso; confirmar campos e limites no Swagger.
  - Verificação: `manual_oficial_e_swagger_confirmados_conteudo_nao_testado`.

- **PNCP — API de Consultas** — tipo: conteudo; método: GET.
  - URL/base: `https://pncp.gov.br/api/consulta/v1/`.
  - [Documentação oficial](https://pncp.gov.br/api/consulta/swagger-ui/index.html).
  - Autenticação: Consulta pública; credenciamento/JWT das APIs de manutenção/publicação não deve ser aplicado automaticamente à API de Consultas.
  - Recursos/paginação: Recursos de consulta e filtros por período, órgão e modalidade conforme Swagger; pagina e tamanhoPagina conforme serviço. Não confundir a API de Consultas com a API de Integração para inserir/alterar/excluir publicações.
  - Verificação: `documentacao_oficial_localizada_conteudo_nao_testado`.

- **Transferegov — Transferências Especiais** — tipo: conteudo; método: Conforme documentação do módulo.
  - URL/base: não registrada; rotas de conteúdo ainda não inspecionadas.
  - [Documentação oficial](https://api-publica.transferegov.gestao.gov.br/especiais/docs).
  - Autenticação: O hub apresenta estes módulos como APIs de dados abertos disponíveis para todos; configuração de segurança por rota não inspecionada.
  - Recursos/paginação: Emendas, pagamentos e execução; filtros de localidade, parlamentar, ano e situação anunciados pelo hub. Caminhos de conteúdo, formatos de resposta e paginação devem ser extraídos da documentação do módulo; não foram inspecionados nesta pesquisa.
  - Verificação: `hub_oficial_e_links_de_documentacao_confirmados_rotas_nao_inspecionadas`.

- **Transferegov — Gestão de Parcerias** — tipo: conteudo; método: Conforme documentação do módulo.
  - URL/base: não registrada; rotas de conteúdo ainda não inspecionadas.
  - [Documentação oficial](https://api-publica.transferegov.gestao.gov.br/parcerias/docs).
  - Autenticação: O hub apresenta estes módulos como APIs de dados abertos disponíveis para todos; configuração de segurança por rota não inspecionada.
  - Recursos/paginação: Programas, parcerias e gestão financeira; filtros de localidade, instrumento, órgão e período anunciados pelo hub. Caminhos de conteúdo, formatos de resposta e paginação devem ser extraídos da documentação do módulo; não foram inspecionados nesta pesquisa.
  - Verificação: `hub_oficial_e_links_de_documentacao_confirmados_rotas_nao_inspecionadas`.

- **Transferegov — Transferências Fundo a Fundo** — tipo: conteudo; método: Conforme documentação do módulo.
  - URL/base: não registrada; rotas de conteúdo ainda não inspecionadas.
  - [Documentação oficial](https://api-publica.transferegov.gestao.gov.br/fundoafundo/docs).
  - Autenticação: O hub apresenta estes módulos como APIs de dados abertos disponíveis para todos; configuração de segurança por rota não inspecionada.
  - Recursos/paginação: Repasses, valores, programas e execução; filtros de localidade, plano de ação e período anunciados pelo hub. Caminhos de conteúdo, formatos de resposta e paginação devem ser extraídos da documentação do módulo; não foram inspecionados nesta pesquisa.
  - Verificação: `hub_oficial_e_links_de_documentacao_confirmados_rotas_nao_inspecionadas`.

- **Transferegov — Termo de Execução Descentralizada (TED)** — tipo: conteudo; método: Conforme documentação do módulo.
  - URL/base: não registrada; rotas de conteúdo ainda não inspecionadas.
  - [Documentação oficial](https://api-publica.transferegov.gestao.gov.br/ted/docs).
  - Autenticação: O hub apresenta estes módulos como APIs de dados abertos disponíveis para todos; configuração de segurança por rota não inspecionada.
  - Recursos/paginação: Termos, valores, órgãos e execução; filtros de órgão, situação e período anunciados pelo hub. Caminhos de conteúdo, formatos de resposta e paginação devem ser extraídos da documentação do módulo; não foram inspecionados nesta pesquisa.
  - Verificação: `hub_oficial_e_links_de_documentacao_confirmados_rotas_nao_inspecionadas`.

- **SIORG — serviços web de estrutura organizacional** — tipo: conteudo; método: GET (REST); SOAP conforme WSDL.
  - URL/base: `https://estruturaorganizacional.dados.gov.br/`.
  - [Documentação oficial](https://siorg.gov.br/manuais/manual-webservices/html/demo_3.html).
  - Autenticação: Serviços disponíveis de forma livre e aberta segundo o manual oficial.
  - Recursos/paginação: REST e SOAP; JSON/XML conforme recurso. O manual documenta /doc/orgao-entidade/resumida e /doc/estrutura-organizacional/alteracoes. Consultar parâmetros por serviço. https://api.siorg.economia.gov.br/ é endereço de documentação, não presumir que seja a base de conteúdo.
  - Verificação: `documentada_sem_teste_http_bem_sucedido`.

- **SIAPE Consultas / Conecta** — tipo: restrita; método: Conforme manual; autenticação por token.
  - URL/base: `https://apigateway.conectagov.estaleiro.serpro.gov.br/api-consulta-siape/v1/consulta-siape`.
  - [Documentação oficial](https://www.gov.br/conecta/catalogo/apis/consulta-siape).
  - Autenticação: Adesão/habilitação de órgão federal, sistemas autorizados, cadastramento de IPs e credenciais/chaves para token conforme manual. Não é API aberta para coleta pública.
  - Verificação: `documentada_acesso_institucional_nao_testado`.

**Arquivos e formatos**

- [Repositório/recurso](https://dados.gov.br/dados/conjuntos-dados/compras-publicas-do-governo-federal) — CSV. Catálogo indicado pelo manual oficial de acesso aos arquivos. Contratações, itens e resultados por período diário, mensal e anual; recursos históricos em diretórios por ano. Descobrir URLs dos recursos no catálogo, não fixar arquivos latest sem registrar competência/hash.
- [Repositório/recurso](https://api-publica.transferegov.gestao.gov.br/downloads) — CSV. Repositório atual indicado pelo hub para Transferências Discricionárias e Legais. API REST desse módulo consta em cronograma de implantação; não foi confirmada como entregue em 03/10/2026.
- [Repositório/recurso](https://www.gov.br/gestao/pt-br/assuntos/gestaoeinovacao/modelos-organizacionais/estruturas-organizacionais/Sistema-informatizado-siorg/sistema-informatizado-siorg/) — JSON. Página oficial de acesso ao SIORG também anuncia arquivos de estruturas em JSON; verificar recurso e data de geração.
- [Repositório/recurso](https://www.gov.br/servidor/pt-br/observatorio-de-pessoal-govbr/painel-estatistico-de-pessoal/) — CSV, Excel. PEP: exportação no painel, inclusive Faça você mesmo. API pública documentada do painel e URL direta estável de exportação automatizada não confirmadas.
- [Repositório/recurso](https://www.gov.br/servidor/pt-br/observatorio-de-pessoal-govbr/gestao-de-pessoas-executivo-federal-gratificacoes) — CSV. Página de publicação encaminha aos conjuntos de gratificações GAEG/GIAPU/GSISP/GSISTE. URLs diretas dos arquivos e competência mais recente não confirmadas.
- [Repositório/recurso](https://www.gov.br/gestao/pt-br/acesso-a-informacao/dados-abertos/planos-de-dados-abertos-pda-vigente-e-anteriores-bem-como-comunicados-de-eventuais-alteracoes-em-seus-conteudos/anexo-mgi/anexo-i-inventario-de-bases-do-mgi-v4.pdf) — CSV conforme dicionário; inventário em PDF. Referência de descoberta, não arquivo de dados: inventário confirma a base aberta Afastamentos e Licenças. O dicionário indica CSV e CPF mascarado; URL direta atual e competência do recurso não confirmadas.
- [Repositório/recurso](https://qlik-publico.paineis.gov.br/extensions/transparencia-ativa/transparencia-ativa.html) — CSV, Excel, GeoJSON indicado pela página. SPU: painel com exportação e link de vetores. Em 03/10/2026 informa atualização 06/03/2026, referência março/2026 e adaptação ao SPUnet; disponibilidade atual dos vetores não testada. Coordenadas geocodificadas; considerar nível de precisão e EPSG 4674.

**Chaves sugeridas:** número de controle PNCP e identificadores de contrato/ata/PCA conforme recurso; UASG e identificador da compra + número do item; CNPJ do órgão/fornecedor como texto e códigos CATMAT/CATSER; identificador de programa/proposta/instrumento/plano de ação no respectivo módulo Transferegov; código da unidade SIORG + vigência/versão da estrutura; competência + órgão/carreira/vínculo nas estatísticas de pessoal; RIP imóvel e RIP utilização nas bases SPU.

**Observações de integração**

- Compras.gov.br reúne dados dos sistemas de compras; PNCP reúne publicações de entes de diferentes esferas. Coberturas não são equivalentes. Há sobreposição: deduplicar por identificadores da contratação/PNCP antes de agregar valores.
- Priorizar a API atual https://dadosabertos.compras.gov.br/. O antigo material de dados abertos Compras apresenta corte até março/2023 e não deve ser usado como evidência de atualização corrente.
- O hub público Transferegov atualmente lista quatro módulos de API; Discricionárias e Legais aparece como CSV. Não tratar cronograma de entrega da API como disponibilidade comprovada nem confundir APIs operacionais institucionais com APIs abertas.
- No Transferegov, documentações /docs foram localizadas, mas rotas de conteúdo não inspecionadas: URL de API permanece nula para evitar fornecer uma rota executável não validada.
- PEP é agregado e tem cobertura/períodos por tema; dados de servidores e ingressos provêm do SIAPE e o painel ressalva exclusão do BCB. API institucional SIAPE não substitui uma API pública do PEP.
- Pessoal: preservar competência e dimensões de órgão/carreira/vínculo; CPF mascarado não é chave confiável para cruzar pessoas. Dicionário de afastamentos: https://repositorio.dados.gov.br/segrt/3.20180928-DadosRecursos-Afastamento.pdf.
- SPU: registrar a defasagem publicada e o aviso de transição ao SPUnet. Não presumir atualização mensal efetiva durante a migração nem tratar coordenadas estimadas como limites cadastrais de imóveis.
- A API de catálogo do Portal Brasileiro de Dados Abertos não foi atribuída ao MGI: localizar um conjunto em dados.gov.br não define a titularidade de sua base.

**Fontes da ficha**

- [Fonte oficial 1](https://www.gov.br/compras/pt-br/acesso-a-informacao/manuais/manual-dados-abertos/manual-api-compras.pdf)
- [Fonte oficial 2](https://www.gov.br/compras/pt-br/acesso-a-informacao/manuais/manual-dados-abertos/ManualdeAcessoaosArquivosdeComprasPblicasGovernoFederal.pdf)
- [Fonte oficial 3](https://www.gov.br/pncp/pt-br/pncp/manuais)
- [Fonte oficial 4](https://www.gov.br/pncp/pt-br/pncp/manuais/versoes-anteriores/ManualPNCPAPIConsultasVerso1.0.pdf)
- [Fonte oficial 5](https://pncp.gov.br/manual/pt-br/latest/acesso_ao_pncp/index.html)
- [Fonte oficial 6](https://api-publica.transferegov.gestao.gov.br/)
- [Fonte oficial 7](https://www.gov.br/transferegov/pt-br/ferramentas-gestao/api-de-dados-abertos-transferegov.br)
- [Fonte oficial 8](https://siorg.gov.br/manuais/manual-webservices/html/demo_3.html)
- [Fonte oficial 9](https://siorg.gov.br/manuais/manual-webservices/html/demo_6.html)
- [Fonte oficial 10](https://siorg.gov.br/manuais/manual-webservices/html/demo_18.html)
- [Fonte oficial 11](https://www.gov.br/servidor/pt-br/observatorio-de-pessoal-govbr/painel-estatistico-de-pessoal/)
- [Fonte oficial 12](https://www.gov.br/servidor/pt-br/observatorio-de-pessoal-govbr/temas-govbr/perfil-de-servidores/tema-perfil-de-servidores)
- [Fonte oficial 13](https://www.gov.br/conecta/catalogo/apis/consulta-siape)
- [Fonte oficial 14](https://www.gov.br/conecta/catalogo/apis/consulta-siape/ws_siape_consultas-pdf)
- [Fonte oficial 15](https://www.gov.br/gestao/pt-br/acesso-a-informacao/dados-abertos/planos-de-dados-abertos-pda-vigente-e-anteriores-bem-como-comunicados-de-eventuais-alteracoes-em-seus-conteudos/anexo-mgi/anexo-i-inventario-de-bases-do-mgi-v4.pdf)
- [Fonte oficial 16](https://repositorio.dados.gov.br/segrt/3.20180928-DadosRecursos-Afastamento.pdf)
- [Fonte oficial 17](https://www.gov.br/servidor/pt-br/observatorio-de-pessoal-govbr/gestao-de-pessoas-executivo-federal-gratificacoes)
- [Fonte oficial 18](https://qlik-publico.paineis.gov.br/extensions/transparencia-ativa/transparencia-ativa.html)
- [Fonte oficial 19](https://www.gov.br/gestao/pt-br/assuntos/patrimonio-da-uniao/transformacao-digital/desligamento-spiunet)


### Tribunal de Contas da União (TCU)

Portal: [fonte oficial](https://sites.tcu.gov.br/dados-abertos/).

**Bases prioritárias**

- Acórdãos e jurisprudência
- Termos contratuais e aditivos do próprio TCU
- Responsáveis inabilitados e licitantes inidôneos
- Contas julgadas irregulares e responsáveis para fins eleitorais

**Obtenção:** Webservices públicos para decisões, contratos do TCU e listas de responsáveis.

**Granularidade:** Acórdão, processo, termo contratual/aditivo ou responsável/sanção.

**Atualização:** Periodicidade não confirmada para todas as bases.

**Interfaces e autenticação**

- **Acórdãos** — tipo: conteudo; método: GET.
  - URL/base: `https://dados-abertos.apps.tcu.gov.br/api/acordao/recupera-acordaos`.
  - [Documentação oficial](https://sites.tcu.gov.br/dados-abertos/webservices-tcu/).
  - Autenticação: Documentação pública consultada não prescreve chave para esses exemplos.
  - Recursos/paginação: inicio e quantidade; paginação por índice.
  - Verificação: `documentada`.
- **Termos contratuais** — tipo: conteudo; método: GET.
  - URL/base: `https://contas.tcu.gov.br/contrata2RS/api/publico/termos-contratuais`.
  - [Documentação oficial](https://sites.tcu.gov.br/dados-abertos/webservices-tcu/).
  - Autenticação: Documentação pública consultada não prescreve chave para esses exemplos.
  - Verificação: `documentada`.
- **Responsáveis / sanções** — tipo: conteudo; método: POST.
  - URL/base: `https://certidoes.apps.tcu.gov.br/api/publico/`.
  - [Documentação oficial](https://sites.tcu.gov.br/dados-abertos/webservices-tcu/).
  - Autenticação: Documentação pública consultada não prescreve chave para esses exemplos.
  - Recursos/paginação: responsaveis-inabilitados; responsaveis-inidoneos; responsaveis-contas-irregulares; responsaveis-fins-eleitorais. Filtros no corpo JSON conforme rota.
  - Verificação: `documentada`.

**Arquivos e formatos**

- [Repositório/recurso](https://sites.tcu.gov.br/dados-abertos/jurisprudencia/) — CSV, PDF, DOC. CSV de acórdãos em conjuntos de anos; API fornece links de documentos.

**Chaves sugeridas:** chave do acórdão; número de processo; CNPJ/identificador do responsável conforme publicação.

**Observações de integração**

- A API de termos contratuais cobre contratos do próprio TCU, não todo o universo fiscalizado.
- A documentação avisa sobre possível indisponibilidade entre 20h e 21h.
- Usar identificadores de documento, processo e responsável conforme base.

**Fontes da ficha**

- [Fonte oficial 1](https://sites.tcu.gov.br/dados-abertos/)
- [Fonte oficial 2](https://sites.tcu.gov.br/dados-abertos/webservices-tcu/)
- [Fonte oficial 3](https://sites.tcu.gov.br/dados-abertos/jurisprudencia/)

### Instituto Brasileiro de Geografia e Estatística (IBGE)

Portal: [fonte oficial](https://servicodados.ibge.gov.br/api/docs/).

**Bases prioritárias**

- SIDRA / agregados de pesquisas e censos: população, PIB, preços, trabalho e outros indicadores
- Localidades e códigos territoriais
- Microdados PNAD Contínua e Censo Demográfico
- Malhas geográficas

**Obtenção:** APIs de agregados/localidades para consultas; repositórios de arquivos para microdados e geografia.

**Granularidade:** Tabela/variável/período/nível territorial; registro amostral nos microdados liberados.

**Atualização:** Varia por pesquisa, tabela e produto. PNAD Contínua trimestral; descobrir períodos disponíveis nos agregados.

**Interfaces e autenticação**

- **Agregados v3** — tipo: conteudo; método: GET.
  - URL/base: `https://servicodados.ibge.gov.br/api/v3/agregados`.
  - [Documentação oficial](https://servicodados.ibge.gov.br/api/docs/agregados?versao=3).
  - Autenticação: Leitura pública; sem token indicado.
  - Recursos/paginação: /{agregado}/metadados; /{agregado}/periodos; /{agregado}/periodos/{periodos}/variaveis/{variavel}?localidades=...
  - Verificação: `documentada`.
- **Localidades** — tipo: conteudo; método: GET.
  - URL/base: `https://servicodados.ibge.gov.br/api/v1/localidades`.
  - [Documentação oficial](https://servicodados.ibge.gov.br/api/docs/).
  - Autenticação: Leitura pública; sem token indicado.
  - Recursos/paginação: /estados e /municipios, entre outros níveis.
  - Verificação: `resposta_estados_verificada`.

**Arquivos e formatos**

- [Repositório/recurso](https://ftp.ibge.gov.br/) — ZIP, TXT, ASCII. Microdados e dicionários por pesquisa/edição.
- [Repositório/recurso](https://geoftp.ibge.gov.br/) — ZIP, Shapefile. Formatos de malhas conforme produto.

**Chaves sugeridas:** código IBGE e nível territorial; identificador de agregado; variável; classificações; período e ano da divisão territorial.

**Observações de integração**

- A API de agregados não fornece automaticamente todos os microdados.
- Localidades são registros/códigos; polígonos exigem malhas.
- Censo 2022: microdados públicos lançados em 2026 têm UF como nível mais desagregado; acesso até área de ponderação é controlado, com Gov.BR e termo.
- Arquivos do Censo 2022 foram corrigidos em setembro/2026; detectar substituições e versões.
- Usar códigos territoriais e ano da divisão territorial; não cruzar somente nomes.

**Fontes da ficha**

- [Fonte oficial 1](https://servicodados.ibge.gov.br/api/docs/)
- [Fonte oficial 2](https://servicodados.ibge.gov.br/api/docs/agregados?versao=3)
- [Fonte oficial 3](https://www.ibge.gov.br/estatisticas/sociais/habitacao/22827-censo-2020-censo4.html)
- [Fonte oficial 4](https://ftp.ibge.gov.br/)

### Instituto de Pesquisa Econômica Aplicada (IPEA)

Portal: [fonte oficial](https://www.ipeadata.gov.br/).

**Bases prioritárias**

- Ipeadata Macroeconômico
- Ipeadata Regional
- Ipeadata Social

**Obtenção:** API REST/OData v4 do Ipeadata.

**Granularidade:** Série/data e, nas bases territoriais, nível e código territorial.

**Atualização:** Por série: consultar PERNOME e SERATUALIZACAO; não há frequência única.

**Interfaces e autenticação**

- **Ipeadata OData v4** — tipo: conteudo; método: GET.
  - URL/base: `https://www.ipeadata.gov.br/api/odata4/`.
  - [Documentação oficial](https://www.ipeadata.gov.br/api/).
  - Autenticação: Consulta pública sem credenciais na inspeção.
  - Recursos/paginação: Metadados, Temas, Territorios, Paises; Metadados('{SERCODIGO}')/Valores ou ValoresSerie(SERCODIGO='{SERCODIGO}'); $metadata em XML. Respeitar capitalização das entidades.
  - Verificação: `documento_servico_json_verificado`.

**Arquivos e formatos**

- [Repositório/recurso](https://www.ipeadata.gov.br/) — Planilhas: extensão atual não confirmada. Extração pelo portal descrita em guia institucional; preferir API para automação.

**Chaves sugeridas:** SERCODIGO; data; nível territorial; código territorial.

**Observações de integração**

- Preservar código da série, unidade, multiplicador, comentários e fonte original.
- Séries regionais/sociais podem exigir nível e código territorial, além de data.
- SERSTATUS identifica séries macroeconômicas ativas/inativas.

**Fontes da ficha**

- [Fonte oficial 1](https://www.ipeadata.gov.br/api/)
- [Fonte oficial 2](https://www.ipeadata.gov.br/api/odata4/)
- [Fonte oficial 3](https://repositorio.ipea.gov.br/bitstream/11058/14491/1/RI_Guia_de_orientacoes_gerais_Ipea.pdf)

### Ministério da Saúde / DATASUS

Portal: [fonte oficial](https://dadosabertos.saude.gov.br/).

**Bases prioritárias**

- CNES: estabelecimentos de saúde
- SIM: mortalidade
- SINASC: nascidos vivos
- SRAG / SIVEP-Gripe
- PNI: doses de vacinação
- SIA/SIH: produção ambulatorial e internações

**Obtenção:** API de conteúdo do Ministério da Saúde para bases cobertas; arquivos DATASUS para séries históricas e conjuntos não cobertos.

**Granularidade:** Estabelecimento CNES; registros públicos anonimizados de óbito/nascimento/notificação/dose e produção assistencial conforme conjunto.

**Atualização:** CNES diário; SINASC anual com prévias; SRAG do ano corrente e PNI 2026 semanais conforme metadados. SIM possui calendário de preliminares/definitivos. Outras bases e competências têm regras próprias.

**Interfaces e autenticação**

- **API Dados Abertos SUS** — tipo: conteudo; método: GET.
  - URL/base: `https://apidadosabertos.saude.gov.br/`.
  - [Documentação oficial](https://apidadosabertos.saude.gov.br/static/swagger.json).
  - Autenticação: CNES explicitamente gratuito sem login/autenticação. Especificação examinada não declara esquema global; autenticação operacional das demais rotas não confirmada.
  - Recursos/paginação: cnes/estabelecimentos; cnes/estabelecimentos/{codigo_cnes}; vigilancia-e-meio-ambiente/sistema-de-informacao-sobre-mortalidade; vigilancia-e-meio-ambiente/sistema-de-informacao-sobre-nascidos-vivos; vigilancia-e-meio-ambiente/srag-2019-2026; vacinacao/doses-aplicadas-pni-2026. limit padrão 100 e máximo 1000; offset descrito como número de página iniciado em zero.
  - Verificação: `openapi_verificado_versao_1.8.32`.

**Arquivos e formatos**

- [Repositório/recurso](https://dadosabertos.saude.gov.br/) — CSV, JSON, XML, Parquet conforme recurso. Catálogo atual; antigo OpenDataSUS redireciona para este portal.
- [Repositório/recurso](https://datasus.saude.gov.br/transferencia-de-arquivos/) — DBC, DBF. DBC é DBF compactado; descobrir recursos/competências na página oficial.
- [Repositório/recurso](https://datasus.saude.gov.br/informacoes-de-saude-tabnet/) — CSV, TabWin. TABNET é tabulação agregada/exportação; não tratar como API REST.

**Chaves sugeridas:** código CNES; código IBGE com correspondência de versões; competência; identificadores públicos do layout.

**Observações de integração**

- Distinguir API de conteúdo de catálogo CKAN; CKAN/DataStore não foi validado nesta pesquisa.
- offset tem semântica de página na documentação examinada; não presumir deslocamento de linhas.
- Separar dado prévio, preliminar, definitivo e congelado; reprocessar versões corrigidas.
- Rotas que contêm ano e versão devem ser redescobertas periodicamente no OpenAPI.
- Não pressupor que todas as tabelas históricas DATASUS estão disponíveis na API nova.

**Fontes da ficha**

- [Fonte oficial 1](https://dadosabertos.saude.gov.br/)
- [Fonte oficial 2](https://apidadosabertos.saude.gov.br/static/swagger.json)
- [Fonte oficial 3](https://www.gov.br/saude/pt-br/acesso-a-informacao/sic/dados-em-transparencia-ativa/seidigi)
- [Fonte oficial 4](https://datasus.saude.gov.br/transferencia-de-arquivos/)
- [Fonte oficial 5](https://dadosabertos.saude.gov.br/dataset/srag-2019-a-2026)

### Agência Nacional de Vigilância Sanitária (ANVISA)

Portal: [fonte oficial](https://www.gov.br/anvisa/pt-br/acessoainformacao/dadosabertos).

**Bases prioritárias**

- Medicamentos registrados
- Produtos para saúde e modelos
- VigiMed e notificações de vigilância
- SNGPC: vendas de medicamentos controlados
- CMED: preços máximos de medicamentos

**Obtenção:** Downloads HTTP de arquivos e dicionários; API pública de conteúdo com contrato estável dessas bases não confirmada.

**Granularidade:** Registro/apresentação de medicamento, produto/modelo, notificação ou venda agregada por dimensões do dicionário.

**Atualização:** Medicamentos registrados: mensal conforme dicionário. SNGPC possui arquivos mensais; frequência das demais bases deve ser confirmada por recurso.

**Interfaces e autenticação**

API pública de conteúdo destas bases não confirmada nesta pesquisa. Isso não afirma que nenhuma interface exista no órgão.


**Arquivos e formatos**

- [Repositório/recurso](https://dados.anvisa.gov.br/dados/) — CSV, XLS, PDF (dicionários). Recursos por conjunto: DADOS_ABERTOS_MEDICAMENTOS.csv, TA_PRODUTO_SAUDE_SITE.csv, VigiMed_Notificacoes.csv e arquivos relacionados.
- [Repositório/recurso](https://dados.anvisa.gov.br/dados/SNGPC/) — Arquivos tabulares por conjunto/competência. Consultar dicionário; revisões podem decorrer de transmissões tardias.
- [Repositório/recurso](https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/cmed/precos) — XLS, CSV conforme recurso. Planilhas de PMC/PMVG e respectivas apresentações.

**Chaves sugeridas:** registro Anvisa; número de processo; CNPJ; código/apresentação do produto; chaves de relacionamento VigiMed; competência.

**Observações de integração**

- Seguir separador, codificação e tipos do dicionário de cada base.
- Data de modificação HTTP/metadados não comprova competência dos registros.
- Alguns arquivos são muito grandes; download em fluxo e carga particionada são propostas de implementação.

**Fontes da ficha**

- [Fonte oficial 1](https://www.gov.br/anvisa/pt-br/acessoainformacao/dadosabertos)
- [Fonte oficial 2](https://dados.anvisa.gov.br/dados/)
- [Fonte oficial 3](https://dados.anvisa.gov.br/dados/Documentacao_e_Dicionario_de_Dados_Registros_Validos_Medicamento_V1.pdf)
- [Fonte oficial 4](https://dados.anvisa.gov.br/dados/SNGPC/)
- [Fonte oficial 5](https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/cmed/precos)

### Agência Nacional de Saúde Suplementar (ANS)

Portal: [fonte oficial](https://www.gov.br/ans/pt-br/acesso-a-informacao/perfil-do-setor/dados-abertos-1).

**Bases prioritárias**

- Operadoras ativas / CADOP
- Beneficiários por operadora / SIB
- Demonstrações contábeis / DIOPS
- Produtos e prestadores hospitalares
- Demandas/reclamações de consumidores

**Obtenção:** Downloads HTTP públicos de arquivos; endpoint público atual da API de operadoras não confirmado.

**Granularidade:** Operadora, vínculo/contagem de beneficiários, conta contábil/período, relação produto/prestador e demanda conforme base.

**Atualização:** Beneficiários por competência mensal; DIOPS contábil trimestral. Frequência atual formal dos demais recursos deve ser conferida.

**Interfaces e autenticação**

- **APIs do Portal Operadoras** — tipo: restrita; método: Conforme rota do serviço..
  - URL/base: não registrada como contrato confirmado.
  - [Documentação oficial](https://www.gov.br/ans/pt-br/centrais-de-conteudo/manuais-do-portal-operadoras/area-do-desenvolvedor/oauth-2.0).
  - Autenticação: OAuth2 client credentials, client ID/secret e Bearer; acesso aos dados próprios da operadora.
  - Recursos/paginação: Não substitui download público de dados setoriais.
  - Verificação: `autenticacao_documentada_nao_testada`.

**Arquivos e formatos**

- [Repositório/recurso](https://dadosabertos.ans.gov.br/FTP/PDA/) — CSV, ZIP, ODS (dicionários). Diretório HTTP; o segmento FTP na URL não é uma API CKAN.
- [Repositório/recurso](https://dadosabertos.ans.gov.br/FTP/PDA/operadoras_de_plano_de_saude_ativas/Relatorio_cadop.csv) — CSV. Cadastro de operadoras ativas.
- [Repositório/recurso](https://dadosabertos.ans.gov.br/FTP/PDA/demonstracoes_contabeis/) — ZIP, ODS. Partições por ano/trimestre; 1T e 2T/2026 observados na pesquisa.

**Chaves sugeridas:** registro ANS da operadora; CNPJ; conta contábil; competência; identificador de produto/prestador conforme layout.

**Observações de integração**

- API JSON de operadoras apareceu em PDA histórico; endpoint público atual não foi confirmado.
- Número de vínculos não equivale necessariamente a número de pessoas únicas.
- Arquivos de beneficiários e produtos podem ter vários gigabytes; observar formatos internos e dicionários.

**Fontes da ficha**

- [Fonte oficial 1](https://www.gov.br/ans/pt-br/acesso-a-informacao/perfil-do-setor/dados-abertos-1)
- [Fonte oficial 2](https://dadosabertos.ans.gov.br/FTP/PDA/)
- [Fonte oficial 3](https://dadosabertos.ans.gov.br/FTP/PDA/demonstracoes_contabeis/)
- [Fonte oficial 4](https://www.gov.br/ans/pt-br/centrais-de-conteudo/manuais-do-portal-operadoras/area-do-desenvolvedor/oauth-2.0)

### Instituto Nacional de Estudos e Pesquisas Educacionais Anísio Teixeira (INEP)

Portal: [fonte oficial](https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/microdados-1).

**Bases prioritárias**

- Censo Escolar
- Censo da Educação Superior
- Enem
- Saeb

**Obtenção:** Downloads de microdados por edição; API pública de conteúdo dessas quatro bases não confirmada nesta pesquisa.

**Granularidade:** Escola, IES/curso, participante ou agregado, conforme edição e dados efetivamente liberados.

**Atualização:** Censos e Enem por edição anual; Saeb por edição. Páginas consultadas publicam Censo Escolar 2025, Enem 2025, Superior 2024 e Saeb 2023; isso não é uma promessa de calendário futuro.

**Interfaces e autenticação**

API pública de conteúdo destas bases não confirmada nesta pesquisa. Isso não afirma que nenhuma interface exista no órgão.


**Arquivos e formatos**

- [Repositório/recurso](https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/microdados-1) — ZIP, CSV, TXT. Pacotes em download.inep.gov.br com dicionários, leia-me e documentação por edição.

**Chaves sugeridas:** código de escola ou IES/curso; ano/edição; identificadores presentes no layout público.

**Observações de integração**

- Granularidade e disponibilidade de registros mudam com anonimização/supressões; ler o dicionário de cada edição.
- Detectar revisões de arquivos e documentação; não presumir registro identificável de aluno/docente.
- SEDAP+ é acesso controlado e não foi confirmado como API pública de microdados.

**Fontes da ficha**

- [Fonte oficial 1](https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/microdados-1)
- [Fonte oficial 2](https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/censo-escolar)
- [Fonte oficial 3](https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/enem)
- [Fonte oficial 4](https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/censo-da-educacao-superior)
- [Fonte oficial 5](https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/saeb)

### Coordenação de Aperfeiçoamento de Pessoal de Nível Superior (CAPES)

Portal: [fonte oficial](https://dadosabertos.capes.gov.br/dataset/).

**Bases prioritárias**

- Programas de pós-graduação stricto sensu
- Docentes e discentes
- Produção intelectual
- Concessão de bolsas a instituições de ensino superior

**Obtenção:** CKAN DataStore nos recursos habilitados; downloads para demais recursos.

**Granularidade:** Programa/IES/ano; registros de docentes/discentes/produção; bolsas por IES/modalidade/ano, conforme recurso.

**Atualização:** Por conjunto/edição; calendários próprios. Recursos consultados incluem discentes 2021–2024 e bolsas 2022–2025.

**Interfaces e autenticação**

- **CKAN DataStore** — tipo: conteudo; método: GET.
  - URL/base: `https://dadosabertos.capes.gov.br/api/3/action/datastore_search`.
  - [Documentação oficial](https://dadosabertos.capes.gov.br/api/1/util/snippet/api_info.html?resource_id=8afca354-18d5-4b6c-9158-2695fb26ad86).
  - Autenticação: Consulta pública sem credenciais na inspeção.
  - Recursos/paginação: resource_id, limit e offset; exemplo resource_id=8afca354-18d5-4b6c-9158-2695fb26ad86 (Discentes 2024).
  - Verificação: `resposta_registros_json_verificada`.
- **CKAN catálogo** — tipo: catalogo; método: GET.
  - URL/base: `https://dadosabertos.capes.gov.br/api/3/action/`.
  - [Documentação oficial](https://dadosabertos.capes.gov.br/dataset/).
  - Autenticação: Consulta pública; funcionamento não confirmado nesta inspeção.
  - Recursos/paginação: package_search/package_show; distinguir dos registros DataStore.
  - Verificação: `funcionamento_nao_confirmado`.

**Arquivos e formatos**

- [Repositório/recurso](https://dadosabertos.capes.gov.br/dataset/) — CSV, XLSX. Documentação PDF/HTML e metadados por conjunto.

**Chaves sugeridas:** código do programa; IES; ano; modalidade.

**Observações de integração**

- DataStore depende do recurso: não presumir que todo arquivo pode ser consultado por registros via API.
- CPF mascarado não fornece uma chave individual completa.
- Preservar código de programa, IES, ano e modalidade quando presentes.

**Fontes da ficha**

- [Fonte oficial 1](https://dadosabertos.capes.gov.br/dataset/)
- [Fonte oficial 2](https://dadosabertos.capes.gov.br/api/1/util/snippet/api_info.html?resource_id=8afca354-18d5-4b6c-9158-2695fb26ad86)
- [Fonte oficial 3](https://dadosabertos.capes.gov.br/api/3/action/datastore_search?limit=5&resource_id=8afca354-18d5-4b6c-9158-2695fb26ad86)
- [Fonte oficial 4](https://dadosabertos.capes.gov.br/dataset/2022-a-2025-concessao-de-bolsas-a-instituicoes-de-ensino-superior-apoiadas-pela-capes)

### Ministério do Trabalho e Emprego (MTE)

Portal: [fonte oficial](https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/estatisticas-trabalho/microdados-rais-e-caged).

**Bases prioritárias**

- RAIS Trabalhador/Vínculos
- RAIS Estabelecimentos
- CAGED Estatístico histórico
- Novo Caged: admissões, desligamentos e saldo de empregos

**Obtenção:** Microdados não identificados por FTP/arquivos; API REST pública dessas bases não confirmada.

**Granularidade:** Vínculo ou estabelecimento na RAIS; movimentação de admissão/desligamento no CAGED.

**Atualização:** RAIS anual; Novo Caged mensal desde janeiro/2020. As séries históricas podem ser revistas.

**Interfaces e autenticação**

API pública de conteúdo destas bases não confirmada nesta pesquisa. Isso não afirma que nenhuma interface exista no órgão.


**Arquivos e formatos**

- [Repositório/recurso](ftp://ftp.mtps.gov.br/pdet/microdados/) — TXT, Arquivos compactados conforme partição. URL publicada pelo MTE; operação FTP não testada. Delimitador ';'; UTF-8 informado para Novo Caged.

**Chaves sugeridas:** competência; código territorial com versão; CNAE; CBO; identificadores públicos do layout.

**Observações de integração**

- Cliente FTP pode ser necessário; navegadores modernos frequentemente não abrem ftp://.
- RAIS 2025 tem divulgação oficial; disponibilidade de cada partição no FTP não foi inspecionada.
- Comunicado Estoque de Referência 2026 registra revisão do estoque Novo Caged desde janeiro/2020.
- Acesso a dados identificados segue autorização/acordo próprio; não confundir com microdados públicos.

**Fontes da ficha**

- [Fonte oficial 1](https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/estatisticas-trabalho/microdados-rais-e-caged)
- [Fonte oficial 2](https://www.gov.br/trabalho-e-emprego/pt-br/acesso-a-informacao/acoes-e-programas/programas-projetos-acoes-obras-e-atividades/estatisticas-trabalho/rais/rais-2025/rais-2025)
- [Fonte oficial 3](https://www.gov.br/trabalho-e-emprego/pt-br/acesso-a-informacao/acoes-e-programas/programas-projetos-acoes-obras-e-atividades/estatisticas-trabalho/comunicados/comunicado-estoque-de-referencia-de-2026)

### Instituto Nacional do Seguro Social (INSS)

Portal: [fonte oficial](https://dadosabertos.inss.gov.br/).

**Bases prioritárias**

- Benefícios concedidos
- Benefícios emitidos e mantidos
- Dados agregados da folha de pagamento
- Requerimentos administrativos solicitados e pendentes

**Obtenção:** Downloads de recursos recentes do catálogo institucional; API pública de catálogo/linhas não confirmada.

**Granularidade:** Microdados públicos sem identificação nominal de benefícios e séries agregadas da folha/requerimentos; não classificar todo o acervo como agregado.

**Atualização:** Mensal por base/competência; conferir o mês publicado no recurso. Recursos consultados incluem concessões e requerimentos até agosto/2026, emitidos até julho/2026 e mantidos até junho/2026.

**Interfaces e autenticação**

- **Benefícios Previdenciários via Conecta** — tipo: restrita; método: GET.
  - URL/base: `https://apigateway.conectagov.estaleiro.serpro.gov.br/api-beneficios-previdenciarios/v3/beneficios`.
  - [Documentação oficial](https://www.gov.br/conecta/catalogo/apis/api-beneficios-previdenciarios).
  - Autenticação: Adesão institucional, credenciais Conecta e liberação de IP no gateway Serpro.
  - Recursos/paginação: Consulta individual por CPF conforme documentação; não é API aberta para beneficiários identificados.
  - Verificação: `documentada_autenticacao_nao_testada`.

**Arquivos e formatos**

- [Repositório/recurso](https://dadosabertos.inss.gov.br/) — CSV, XLSX, ZIP. Recursos mensais de benefícios e requerimentos. Slugs antigos podem conter anos encerrados apesar de recursos atuais.

**Chaves sugeridas:** competência; espécie de benefício; código territorial com correspondência; unidade administrativa; identificadores públicos do layout.

**Observações de integração**

- Preferir catálogo recente a páginas antigas limitadas a 2018–2021.
- Microdados sem identificação nominal não autorizam inferência de cadastro individual identificado.
- Não foi confirmada API CKAN de catálogo/consulta de linhas; não usar rota presumida como contrato verificado.

**Fontes da ficha**

- [Fonte oficial 1](https://www.gov.br/inss/pt-br/acesso-a-informacao/dados-abertos/dados-abertos)
- [Fonte oficial 2](https://dadosabertos.inss.gov.br/)
- [Fonte oficial 3](https://dadosabertos.inss.gov.br/pt_BR/dataset/beneficios-concedidos-plano-de-dados-abertos-jun-2023-a-jun-2025)
- [Fonte oficial 4](https://dadosabertos.inss.gov.br/dataset/dados-agregados-da-folha-de-pagamento-beneficios-emitidos-plano-de-dados-abertos-jun-2023-a-jun-2027)
- [Fonte oficial 5](https://www.gov.br/conecta/catalogo/apis/api-beneficios-previdenciarios)

### Instituto Nacional de Pesquisas Espaciais (INPE)

Portal: [fonte oficial](https://terrabrasilis.dpi.inpe.br/).

**Bases prioritárias**

- PRODES: desmatamento
- DETER: alertas de desmatamento
- Queimadas: focos de fogo ativo
- Área queimada, eventos de fogo e risco de fogo

**Obtenção:** WFS para feições vetoriais publicadas; downloads de arquivos geoespaciais e tabelas conforme produto.

**Granularidade:** Polígono/feição, pixel ou foco de fogo, com referência temporal e produto.

**Atualização:** PRODES anual; DETER diário conforme FAQ. Queimadas tem produtos em intervalos de minutos, horários, diários e mensais.

**Interfaces e autenticação**

- **TerraBrasilis WFS** — tipo: geoespacial_conteudo; método: GET.
  - URL/base: `https://terrabrasilis.dpi.inpe.br/geoserver/ows`.
  - [Documentação oficial](https://terrabrasilis.dpi.inpe.br/faq/).
  - Autenticação: Produtos publicados são públicos; acesso antecipado DETER é restrito.
  - Recursos/paginação: GetCapabilities para descobrir camadas; DescribeFeatureType para atributos; GetFeature para feições. Verificar count/startIndex/sortBy, CRS e limite anunciado pelo serviço.
  - Verificação: `documentada_capabilities_nao_inspecionado`.

**Arquivos e formatos**

- [Repositório/recurso](https://terrabrasilis.dpi.inpe.br/geonetwork/srv/search?type=dataset) — Shapefile, GeoPackage, GeoTIFF. GeoNetwork é catálogo de metadados; formatos por produto.
- [Repositório/recurso](https://terrabrasilis.dpi.inpe.br/queimadas/portal/dados-abertos/) — CSV, KML, TIFF, Shapefile, GeoPackage. Produtos de focos, área queimada e eventos têm formatos e maturidade próprios.

**Chaves sugeridas:** identificador da feição; data; produto/satélite; geometria e CRS.

**Observações de integração**

- WMS fornece mapas para visualização; WFS fornece feições vetoriais.
- Nomes atuais de camadas não confirmados; descobri-los no serviço e não fixar um exemplo antigo.
- Não substituir PRODES consolidado por soma de alertas DETER.
- Registrar satélite, data, resolução, CRS e maturidade/revisão do produto.

**Fontes da ficha**

- [Fonte oficial 1](https://terrabrasilis.dpi.inpe.br/faq/)
- [Fonte oficial 2](https://terrabrasilis.dpi.inpe.br/geonetwork/srv/search?type=dataset)
- [Fonte oficial 3](https://terrabrasilis.dpi.inpe.br/queimadas/portal/dados-abertos/)

### Ministério da Justiça e Segurança Pública (MJSP / SINESP)

Portal: [fonte oficial](https://www.gov.br/mj/pt-br/acesso-a-informacao/dados-abertos).

**Bases prioritárias**

- Dados Nacionais de Segurança Pública / SINESP VDE
- Pesquisa Perfil das Instituições de Segurança Pública

**Obtenção:** Downloads de bases e notas metodológicas; API pública de conteúdo VDE/Perfil não confirmada.

**Granularidade:** UF/município/mês/indicador no VDE; UF/instituição/ano na Pesquisa Perfil.

**Atualização:** VDE alimentado mensalmente pelos estados, sujeito a validação e retificação. Pesquisa Perfil anual, mas a atualização anual de seu ZIP público não foi confirmada.

**Interfaces e autenticação**

API pública de conteúdo destas bases não confirmada nesta pesquisa. Isso não afirma que nenhuma interface exista no órgão.


**Arquivos e formatos**

- [Repositório/recurso](https://dados.mj.gov.br/) — XLSX, ZIP, PDF (dicionários e notas). Catálogo apresentou erro de obtenção nesta pesquisa; isso não prova indisponibilidade permanente.
- [Repositório/recurso](https://www.gov.br/mj/pt-br/assuntos/sua-seguranca/seguranca-publica/estatistica/dados-nacionais-1/base-de-dados-e-notas-metodologicas-dos-gestores-estaduais-sinesp-vde-2022-e-2023) — XLSX, ZIP conforme recurso. Página vigente com bases/notas 2015–2026; título/slug antigo não determina a cobertura atual.
- [Repositório/recurso](https://www.gov.br/mj/pt-br/assuntos/sua-seguranca/seguranca-publica/estatistica/pesquisaperfil/base-de-dados-pesquisa-perfil) — ZIP. Download histórico 2004–2019 observado; base estruturada recente não confirmada.

**Chaves sugeridas:** território e código conforme layout; mês/ano; indicador; unidade de medida; instituição.

**Observações de integração**

- Guardar notas estaduais e critérios de consolidação.
- A página atual alerta para linhas de tentativas de homicídio/estupro que devem ser somadas; não eliminá-las automaticamente como duplicadas.
- SINESP Infoseg é serviço operacional de acesso credenciado; não integra dados abertos nem autoriza coleta pública de registros individuais.

**Fontes da ficha**

- [Fonte oficial 1](https://www.gov.br/mj/pt-br/acesso-a-informacao/dados-abertos)
- [Fonte oficial 2](https://dados.mj.gov.br/dataset/sistema-nacional-de-estatisticas-de-seguranca-publica)
- [Fonte oficial 3](https://www.gov.br/mj/pt-br/assuntos/sua-seguranca/seguranca-publica/estatistica/dados-nacionais-1/base-de-dados-e-notas-metodologicas-dos-gestores-estaduais-sinesp-vde-2022-e-2023)
- [Fonte oficial 4](https://www.gov.br/mj/pt-br/assuntos/sua-seguranca/seguranca-publica/estatistica/pesquisaperfil/base-de-dados-pesquisa-perfil)
- [Fonte oficial 5](https://www.gov.br/mj/pt-br/assuntos/sua-seguranca/seguranca-publica/sinesp-1/sinesp-infoseg)

### Câmara dos Deputados

Portal: [fonte oficial](https://dadosabertos.camara.leg.br/).

**Bases prioritárias**

- Deputados e histórico parlamentar
- Proposições e tramitações
- Votações e votos individuais
- Despesas da Cota para o Exercício da Atividade Parlamentar (CEAP)

**Obtenção:** API REST v2 para consultas; arquivos históricos por conjunto/ano/legislatura.

**Granularidade:** Parlamentar, proposição, tramitação, votação, voto e documento de despesa.

**Atualização:** Principais arquivos possuem atualização diária documentada; dados da API conforme sistemas de origem.

**Interfaces e autenticação**

- **Dados Abertos v2** — tipo: conteudo; método: GET.
  - URL/base: `https://dadosabertos.camara.leg.br/api/v2/`.
  - [Documentação oficial](https://dadosabertos.camara.leg.br/swagger/api.html).
  - Autenticação: Documentação de leitura não exige chave.
  - Recursos/paginação: deputados; deputados/{id}/despesas; proposicoes; proposicoes/{id}/tramitacoes; votacoes; votacoes/{id}/votos. Paginação padrão 15 e máximo 100 itens conforme documentação consultada.
  - Verificação: `openapi_verificado_payload_dados_nao_inspecionado`.

**Arquivos e formatos**

- [Repositório/recurso](https://dadosabertos.camara.leg.br/arquivos/) — CSV, JSON, XML, XLSX, ODS, ZIP. Disponibilidade por conjunto; CEAP usa também www.camara.leg.br/cotas/Ano-{ano}.{formato}[.zip].

**Chaves sugeridas:** id do deputado; id da proposição; id da votação; identificador do documento de despesa.

**Observações de integração**

- Sem filtro temporal, deputados tende a cobrir exercício atual e despesas a janela recente; explicitar datas.
- Coletores precisam seguir paginação e links retornados.
- O esquema CEAP difere entre API e arquivos; comparar chaves antes de mesclar.
- Documentação informa API incompleta e sujeita a mudanças.

**Fontes da ficha**

- [Fonte oficial 1](https://dadosabertos.camara.leg.br/swagger/api.html)
- [Fonte oficial 2](https://dadosabertos.camara.leg.br/api/v2/api-docs)
- [Fonte oficial 3](https://dadosabertos.camara.leg.br/arquivos/)

### Senado Federal

Portal: [fonte oficial](https://www12.senado.leg.br/dados-abertos).

**Bases prioritárias**

- Senadores, mandatos e filiações
- Matérias legislativas e tramitações
- Votações nominais
- CEAPS: cota parlamentar
- Contratos e licitações administrativas

**Obtenção:** API legislativa e API administrativa separadas; arquivos conforme conjunto.

**Granularidade:** Senador, matéria, votação e registro administrativo conforme serviço.

**Atualização:** Legislativo informa atualização online; CEAPS e contratos, diária.

**Interfaces e autenticação**

- **API legislativa** — tipo: conteudo; método: GET.
  - URL/base: `https://legis.senado.leg.br/dadosabertos/`.
  - [Documentação oficial](https://legis.senado.leg.br/dadosabertos/docs/).
  - Autenticação: Consulta de lista de senadores realizada sem credenciais.
  - Recursos/paginação: Exemplo senador/lista/atual.json; formatos e filtros variam por serviço.
  - Verificação: `resposta_registros_json_verificada`.
- **API administrativa** — tipo: conteudo; método: GET.
  - URL/base: `https://adm.senado.gov.br/adm-dadosabertos/api/v1/`.
  - [Documentação oficial](https://adm.senado.gov.br/adm-dadosabertos/swagger-ui/index.html?configUrl=/adm-dadosabertos/swagger-config.json).
  - Autenticação: Consultar documentação de cada rota pública; teste autenticado não realizado.
  - Recursos/paginação: CEAPS e outros conjuntos administrativos: localizar rota detalhada no Swagger; rota específica de documentos de despesa não confirmada nesta pesquisa.
  - Verificação: `documentada_rota_despesa_nao_confirmada`.

**Arquivos e formatos**

- [Repositório/recurso](https://www12.senado.leg.br/dados-abertos) — CSV, JSON, XML. Formatos e disponibilidade por conjunto; CEAPS catalogado em CSV e Web Service.

**Chaves sugeridas:** código de senador; código de matéria; identificador de votação; ano/documento CEAPS conforme layout.

**Observações de integração**

- CEAPS é administrativo e não deve ser atribuído à API legislativa.
- Um relatório consolidado de recursos utilizados não equivale ao detalhamento de documentos CEAPS.
- O CSV de votações de senador tem janela de 12 meses; verificar serviço/filtro para histórico completo.

**Fontes da ficha**

- [Fonte oficial 1](https://www12.senado.leg.br/dados-abertos)
- [Fonte oficial 2](https://legis.senado.leg.br/dadosabertos/docs/)
- [Fonte oficial 3](https://legis.senado.leg.br/dadosabertos/senador/lista/atual.json)
- [Fonte oficial 4](https://adm.senado.gov.br/adm-dadosabertos/swagger-ui/index.html?configUrl=/adm-dadosabertos/swagger-config.json)

### Conselho Nacional de Justiça (CNJ)

Portal: [fonte oficial](https://www.cnj.jus.br/sistemas/datajud/api-publica/).

**Bases prioritárias**

- DataJud: processos, classes, assuntos, órgãos julgadores e movimentos
- Justiça em Números / SIESPJ: indicadores e séries estatísticas

**Obtenção:** API DataJud por tribunal; arquivos estatísticos publicados pelo CNJ para Justiça em Números.

**Granularidade:** Processo e movimentos; indicadores por ramo/tribunal/ano nas bases estatísticas.

**Atualização:** A remessa diária foi determinada em agosto/2026 com prazo de 180 dias para adequação; em 03/10/2026 não comprova atualização diária efetiva de todos os tribunais.

**Interfaces e autenticação**

- **DataJud** — tipo: conteudo; método: POST.
  - URL/base: `https://api-publica.datajud.cnj.jus.br/`.
  - [Documentação oficial](https://datajud-wiki.cnj.jus.br/api-publica/endpoints/).
  - Autenticação: Authorization: APIKey {chave pública vigente}; a chave pode ser substituída pelo CNJ.
  - Recursos/paginação: Alias por tribunal; exemplo api_publica_trf1/_search. Query DSL em JSON; paginação search_after conforme documentação.
  - Verificação: `documentada_autenticacao_nao_testada`.

**Arquivos e formatos**

- [Repositório/recurso](https://www.cnj.jus.br/base-de-dados/) — CSV. Bases estatísticas por ramo/tribunal/ano; não foi confirmado dump nacional atualizado do DataJud.

**Chaves sugeridas:** identificador do processo; tribunal; grau; órgão julgador; classe e assuntos TPU.

**Observações de integração**

- DataJud não inclui integralmente conteúdo de processos sigilosos; dados podem ser excluídos/anonimizados.
- A Portaria 374/2026 restringe uso a fins legais, não comerciais e autorizados; veda modificação, distribuição, venda ou exploração comercial e exige citar CNJ/DataJud. Registrar e avaliar essas condições antes de integrar/redistribuir.
- Precisão, integridade e atualidade dependem das remessas dos tribunais.
- Não confundir os registros processuais chamados metadados com uma API de catálogo.

**Fontes da ficha**

- [Fonte oficial 1](https://datajud-wiki.cnj.jus.br/api-publica/endpoints/)
- [Fonte oficial 2](https://datajud-wiki.cnj.jus.br/api-publica/acesso/)
- [Fonte oficial 3](https://atos.cnj.jus.br/atos/detalhar/6972)
- [Fonte oficial 4](https://www.cnj.jus.br/base-de-dados/)

## Abordagens para o pipeline

- **Híbrida: APIs oficiais e arquivos em lote — recomendada**. APIs para consultas filtradas/atualizações e downloads para histórico ou conjuntos sem API. Descobrir recursos pelos catálogos e validar esquema, competência e condições de reutilização. Maior cobertura; requer adaptadores HTTP/REST/OData/WFS/FTP e parsers de formatos diferentes.
- **Somente APIs de conteúdo**. Começar pelas famílias de API de BCB, IBGE, IPEA, STN, CGU, MGI (Compras.gov.br, PNCP, Transferegov e SIORG), TCU, Ministério da Saúde, Legislativo e recursos CAPES. Menor variedade de parsers, mas cobre parcialmente órgãos que publicam predominantemente arquivos.
- **Arquivos em lote como base principal**. Carregar competências/edições publicadas e utilizar APIs apenas para enriquecimento/consultas pontuais. Boa reprodutibilidade de cargas históricas, com maior volume de armazenamento e maior defasagem em algumas bases.

## Ordem inicial proposta

1. Fundação: IBGE Localidades, SIORG/MGI e tabelas de correspondência de códigos territoriais e unidades administrativas.
2. Primeiros adaptadores de API: BCB, IBGE Agregados, IPEA, STN Siconfi e Câmara/Senado.
3. Transparência e gestão: CGU com token, TCU e MGI (Compras.gov.br, PNCP e Transferegov); usar downloads na carga completa e deduplicar compras publicadas em mais de uma fonte.
4. Saúde e educação: API MS e CAPES DataStore; depois arquivos DATASUS/INEP/ANS/ANVISA.
5. Cadastros e séries extensas: RFB CNPJ, MTE e INSS por competências; incorporar revisões.
6. Geografia e justiça: INPE com descoberta de camadas e CNJ condicionado às regras atuais de reutilização.

## Contrato proposto para coleta

- Identificar órgão, conjunto, recurso, competência e fonte oficial.
- Separar data de referência, atualização da fonte e data de coleta.
- Registrar URL, método, parâmetros não secretos, versão do esquema, hash do arquivo e execução.
- Preservar arquivos/respostas originais e normalizar em camada separada.
- Tratar paginação, limites, retomada e reprocessamento de competências corrigidas.
- Representar identificadores como texto; conservar códigos originais e tabelas de correspondência.
- Validar granularidade e cardinalidade antes de somar ou cruzar bases.
- Registrar licença/condições de reutilização por conjunto e distinguir acesso público de acesso restrito.

Estas propostas são desenho de referência. Este mapeamento não implementa coletores nem afirma cobertura exaustiva ou disponibilidade contínua dos serviços.
