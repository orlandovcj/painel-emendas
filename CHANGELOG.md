# Changelog

Todo o histórico de alterações deste projeto será documentado neste arquivo.

O formato é baseado no [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/) e este projeto segue a convenção de [Versionamento Semântico](https://semver.org/lang/pt-BR/).

---

## [1.9.0] - 2026-10-09

### Adicionado

- **Alerta de Transferência para Contas da Prefeitura (Mesma Titularidade)**:
  - Adicionado alerta em destaque na **Visão por Município**, posicionado logo abaixo dos cards de resumo na seção *"💸 Movimentações Financeiras da Conta Corrente (Transferegov API)"*.
  - Detecção automática de saídas da conta da emenda destinadas a outras contas da própria administração municipal (`TEV MESM T`, transferências para o mesmo CNPJ ou titularidade da prefeitura).
  - Exibição do valor total transferido, quantidade de operações e identificação dos dados bancários de destino (banco, agência e conta).
  - Texto orientativo contextualizando a importância do controle financeiro (ressaltando que pagamentos a fornecedores devem partir diretamente da conta da emenda e contextualizando retenções tributárias de IRRF, INSS, ISS).
  - Tabela expansível (*expander*) com o histórico completo das transferências internas (data, valor, descrição e dados bancários de destino).
- **Identificação de Contas Compartilhadas e Dados Bancários**:
  - Inclusão das colunas **Banco**, **Agência**, **Conta Corrente** e **Conta Compartilhada** (`Sim` / `Não`) na tabela *"Detalhamento dos Pagamentos por Emenda"* na Visão por Empresa, permitindo auditar visualmente a conta bancária exata de onde partiram os recursos.
  - Nota explicativa na interface informando quando os valores exibidos decorrem de rateio proporcional ponderado entre parlamentares.

### Corrigido

- **Correção de Duplicidade em Contas Bancárias Compartilhadas (Rateio Proporcional Ponderado)**:
  - Correção da falha que multiplicava integralmente o valor dos pagamentos de uma conta corrente para todas as emendas vinculadas a ela quando um município utilizava uma conta única para múltiplos parlamentares.
  - Implementação de algoritmo de rateio ponderado pelo aporte financeiro de cada emenda na conta (`Peso = Valor da Emenda / Total de Emendas na Conta`), garantindo conciliação 100% exata com os débitos reais do extrato bancário.
  - Atualização do script `atualizar_pagamentos_pj.py` e recálculo da base `dados/pagamentos_pj.csv`, eliminando distorções de valores artificialmente duplicados.
- **Eliminação de Aplicações Financeiras, Bancos e Tarifas da Base de Pagamentos PJ**:
  - Identificação e expurgo de aplicações financeiras automáticas de saldo parado (como `BB-APLIC C.PRZ-APL.AUT` do Banco do Brasil, que somava indevidamente R$ 72,4 milhões) e tarifas bancárias (Caixa Econômica Federal) que figuravam erroneamente como empresas fornecedoras.
  - Aperfeiçoamento da filtragem de PJs em `atualizar_pagamentos_pj.py` (`is_pj_transaction`) e em `app.py` (`is_pj_debit`), excluindo instituições financeiras, fundos de investimento, tarifas de transferência e entes públicos da listagem de credores.
  - O ranking de maiores fornecedores de Santa Catarina agora reflete com precisão exclusivamente empresas privadas de construção civil, pavimentação, máquinas e serviços.

---

## [1.8.1] - 2026-10-07

### Corrigido

- **Correção da Métrica de Volume no Panorama Geral de Fornecedores**:
  - Substituição da métrica "Total Movimentado" (que incorria em duplicidade ao somar os saques/débitos em extrato com as reservas orçamentárias de empenho no TCE-SC) por **Total Pago (Extratos do Transferegov)**.
  - **Top 15 Fornecedores**: Ranking e barras agora ordenados e calculados estritamente pelo volume efetivamente pago nas contas bancárias das emendas via Transferegov.
  - **Card Maior Fornecedor do Estado**: Atualizado para refletir o maior credor por recursos efetivamente pagos via Transferegov.
  - **Tabela Geral de Fornecedores**: Reestruturação das colunas financeiras com *Total Pago (Extratos do Transferegov) (R$)*, *Total Empenhado TCE (R$)* e *Total Pago TCE (R$)*, eliminando a soma duplicada.

---

## [1.8.0] - 2026-10-07

### Adicionado

- **Suporte a Mapa Coroplético (Polígonos Municipais)**:
  - Adicionado seletor de visualização na seção "Raio de Ação Geográfico: Presença em SC" permitindo alternar entre **🗺️ Polígonos Municipais (Coroplético)** e **📍 Bolhas Proporcionais (Scatter)**, com polígonos municipais definidos como padrão.
  - Integração e carregamento com cache em memória (`@st.cache_data`) da malha cartográfica oficial de Santa Catarina a partir de `dados/geojs-SC-mun.json` via correspondência de códigos do IBGE (`properties.id`).
- **Desmembramento dos Indicadores de Execução Contábil (TCE-SC)**:
  - Criação de card de KPI dedicado para **Total Pago (TCE-SC)** (valores liquidados e pagos informados ao Tribunal de Contas), posicionado logo abaixo do card **Total Empenhado (TCE-SC)**.
- **Reestruturação em Grade 2×2 na Aba 📍 Presença Geográfica**:
  - Organização do espaço em duas colunas e duas linhas com 3 gráficos dedicados e 1 tabela comparativa:
    - Gráfico *Valores Empenhados (Fonte: TCE-SC)* (escala `YlOrRd`).
    - Gráfico *Valores Pagos (Fonte: TCE-SC)* (escala `Tealgrn`).
    - Gráfico *Valores Pagos - Débitos Bancários (Fonte: Transferegov)* (escala `Blues`).
    - Tabela comparativa consolidada por município.
- **Gráfico de Evolução Anual dos Recursos (TCE-SC vs Transferegov)**:
  - Gráfico temporal comparativo com curvas suaves (*spline*) e área translúcida (*fill tozeroy*), demonstrando ano a ano os valores empenhados no TCE-SC, pagos no TCE-SC e saídas de conta no Transferegov.
- **Tabela de Evolução Mensal dos Recursos**:
  - Nova tabela detalhada mês a mês (`MM/AAAA`) na aba de comparação, apresentando: *Mes/Ano*, *Empenhado (TCE-SC)*, *Pago (TCE-SC)*, *Debitado em Conta (Transferegov)* e *Divergência (R$)*.
  - Criação da base de suporte indexada `dados/pagamentos_mensais_cache.json` para consulta em milissegundos dos débitos bancários mensais por empresa.

### Modificado

- **Reorganização da Aba de Comparação**:
  - Renomeada para **⚖️ Comparação: TCE-SC vs Transferegov**.
  - Reordenação da seção para melhor fluxo de auditoria: 1) Gráfico comparativo por município, 2) Tabela de conciliação por município, 3) Gráfico de evolução anual e 4) Tabela de evolução mensal.
- Padronização de paletas visuais e formatação monetária localizada no padrão brasileiro em todos os novos componentes.

---

## [1.7.0] - 2026-10-07

### Adicionado

- **Novo Modo de Análise por Empresa/Fornecedor**: Inclusão de seletor de perspectiva na barra lateral ("📍 Visão por Município" vs "🏢 Visão por Empresa").
- **Raio-X Completo da Empresa**:
  - Mapa interativo de Santa Catarina com o **Raio de Ação Geográfico** destacando apenas as cidades onde a empresa atuou.
  - Aba **📍 Presença Geográfica**: Ranking e tabela com as principais prefeituras contratantes.
  - Aba **🏛️ Origem Parlamentar**: Distribuição dos recursos por parlamentar autor da emenda e indicador de dependência política.
  - Aba **⚖️ Auditoria TCE-SC vs Transferegov**: Gráfico comparativo e tabela de conciliação entre execução orçamentária contábil e saídas financeiras de conta.
  - Aba **📝 Obras e Contratos Detalhados**: Listagem estruturada de todos os empenhos, editais e objetos da empresa no TCE-SC.
- Otimização de performance: cache temporal (TTL de 30 dias) para extratos bancários das contas de emendas no script de coleta.
- Otimização: verificação e sincronização automática de novas contas correntes e novas emendas na API do Transferegov.

### Modificado

- **Ordenação Numérica e Formatação Monetária no Padrão Brasileiro**: Configuração de `st.column_config.NumberColumn(format="localized", step=0.01)` em todas as 11 tabelas do painel, garantindo que os valores monetários sejam exibidos no padrão brasileiro (ponto como separador de milhar e vírgula como separador decimal com duas casas decimais, ex.: `1.234.567,89`) preservando a ordenação matemática natural ao clicar nos cabeçalhos das colunas.
- **Layout do Painel de Empresas**: Alinhamento dos cartões de métricas (KPIs) em uma coluna à direita ([7, 3]), posicionados ao lado do mapa interativo/gráfico geral, harmonizando o design com o painel de visão geral dos municípios.
- **Navegação e Reset de Seleção**: Sincronização bidirecional do seletor da barra lateral com os botões "Voltar ao panorama geral de empresas" e "Resetar Seleção", garantindo que a empresa seja desmarcada e a visualização retorne ao Panorama Geral de Empresas.
- Adição de novos parâmetros para controle de cache no script de atualização: `--dias-expiracao` (padrão: 30 dias).
- Padronização da exibição de documentos nas tabelas da aba **🏢 Empresas Contratadas** ("Lista de Empresas Habilitadas e Contratadas" e "Pagamentos às empresas (Extratos)"): formato `99.999.999/9999-99` para CNPJ e `999.999.999-99` para CPF.

---

## [1.6.0] - 2026-08-10

### Adicionado

- Integração da base de pagamentos a pessoas jurídicas a partir do arquivo local `pagamentos_pj.csv`.
- Nova seção **Pagamentos às empresas (Extratos)** na aba **🏢 Empresas Contratadas**, contendo uma tabela detalhada com CNPJ, Razão Social e Valor total pago agrupado para o município filtrado.
- Gráfico de barras horizontais na aba **🏢 Empresas Contratadas** apresentando o ranking das **Top 5 empresas** beneficiárias de pagamentos (com base em `pagamentos_pj.csv`).
- Filtro anual para a base de pagamentos baseado nos primeiros 4 dígitos do `Código da Emenda`.

---

## [1.5.0] - 2026-07-31

### Adicionado

- Integração de dados bancários offline a partir da nova fonte de dados `emendas_sc.csv`.
- Resiliência offline para exibição imediata de banco, agência e conta corrente das emendas selecionadas sem a necessidade de requisições de rede preliminares.
- Suporte para anos históricos adicionais (2020 e 2021) no painel, expandindo o volume total de emendas cadastradas de 177 para 212 emendas únicas (3.611 registros).
- Integração do motor de similaridade de licitações com o objeto pactuado local das emendas (offline) como fallback quando a API do Transferegov estiver lenta ou indisponível.
- Auditoria cruzada na listagem de licitações associadas: licitações municipais cujos contratados constam como beneficiários de retiradas/débitos na conta bancária da emenda são forçadamente listadas (passando por cima do limiar de similaridade de texto) e marcadas com a origem "Empresa Beneficiária de Pagamento" e seus dados de CNPJ/CPF.

### Modificado

- Substituição da fonte de dados local das emendas de `emendas-por-favorecido.csv` para `emendas_sc.csv`.
- Carregamento automático e otimizado na consulta de extratos (lançamentos financeiros): a consulta do extrato é realizada automaticamente ao selecionar uma emenda na tabela, eliminando a necessidade do clique em um botão manual. A consulta é feita diretamente a partir dos dados bancários do CSV local, reduzindo a latência e dispensando a necessidade das consultas prévias de busca de plano e executor do Transferegov.
- Padronização e higienização dos campos numéricos bancários e códigos parlamentares durante a importação em `load_data()`.
- Atualização da documentação no `README.md` refletindo a nova fonte de dados de emendas e seus campos bancários locais.

---

## [1.4.0] - 2026-07-26

### Adicionado

- Documentação da Aba 4 ("Detalhes e Histórico Textual") no `README.md`.

### Modificado

- Fonte de dados dos empenhos atualizada para a planilha `TCE_empenhos_obras_mat_permanentes_tranferencias_especiais.xlsx` extraída do Portal Farol do TCE-SC. Esta planilha abrange todos os empenhos municipais catarinenses custeados pelas Transferências Especiais da União (Emendas PIX) que foram aplicados tanto em obras quanto em aquisição de materiais permanentes, ampliando o escopo do painel analítico.
- Atualização das referências no `README.md` sobre a nova fonte de dados de empenhos e nomenclatura das abas correspondentes na interface da aplicação.

---

## [1.3.0] - 2026-07-24

### Adicionado

- Extrato de movimentações financeiras ao vivo da conta bancária da emenda (Aba 1) consultando a API pública do Transferegov.
- Gráfico de barras horizontais detalhando a distribuição dos débitos (saídas) destinados a PJs no extrato de conta da emenda, ordenados decrescentemente.
- Seletor de período por múltiplos anos na barra lateral (`st.sidebar.multiselect`), permitindo filtros de anos individuais ou combinados sobre o painel.
- Informação sobre o momento da última atualização das bases locais de dados (Emendas, Empenhos e Licitações) exibida na barra lateral.
- Suporte a paginação automática (`while page <= total_pages`) para ler e consolidar todos os registros de transações de extrato (200 itens por página).
- Arquivo de configuração de diretórios de versionamento `.gitignore` para o ecossistema Python/Streamlit.

### Modificado

- Processo de formatação do número de documento (CNPJ/CPF) no extrato financeiro da emenda, padronizando a exibição e o padding de zeros à esquerda (zeros suprimidos) para 14 dígitos (CNPJ) ou 11 dígitos (CPF).
- A base de dados de licitações locais agora retém e extrai o campo `ano_licitacao` a partir do número do edital ou datas da licitação para compatibilidade com o filtro anual.
- Arquivo de dependências `requirements.txt` atualizado para incluir o pacote `requests`.

### Corrigido

- Refinado o leitor de data mais recente das licitações para avaliar especificamente a coluna `"Data Envio Licitação"`.

---

## [1.2.0] - 2026-07-24

### Adicionado

- Sistema de busca de editais de licitação locais por similaridade combinada, cruzando simultaneamente o objeto da emenda do Transferegov e as descrições dos empenhos municipais associados.
- Algoritmo de Jaccard Ponderado (Weighted Jaccard / MinMax) para comparação textual avançada.
- **Location Weight Boosting**: Ponderação especial de similaridade com peso alto ($4.0$) para nomes de ruas, avenidas, rodovias, estradas ou bairros, mitigando falsos positivos em obras de pavimentação.
- Exposição do campo "Origem da Similaridade" na listagem de licitações associadas.

### Modificado

- Assinatura e parâmetros da função `fetch_transferegov_data` atualizados para extrair o CNPJ da prefeitura e realizar o filtro direto na consulta do plano de ação (`cnpj_beneficiario_plano_acao`).

---

## [1.1.0] - 2026-07-24

### Adicionado

- Integração em tempo real com a API oficial do Transferegov para carregar dados do executor, objeto pactuado, situação do plano de ação e dados bancários da emenda parlamentar na Aba 1.
- Inclusão da coluna "Descrição do Objeto" (derivada do campo `Descrição Histórico Empenho` do Excel do TCE-SC) na tabela principal de empenhos de obras da Aba 2.

### Modificado

- Reestruturação das tabelas de auditoria da Aba 2 para incluir campos separados estruturados de Licitação (ex: `TP18/2023`) e Contrato (ex: `68/2023`).

### Corrigido

- Ajustado o divisor dinâmico de códigos de licitações e contratos via expressão regular `re.split(r'\s+/\s+', ...)` para preservar a integridade de formatação com barras.

---

## [1.0.0] - 2026-07-24

### Adicionado

- Versão inicial do Painel Interativo de Emendas e Obras de SC.
- Mapa coroplético e de dispersão geográfico interativo de Santa Catarina (`plotly.express.scatter_map`) com tamanho das bolhas proporcional aos recursos recebidos e cores indicativas da taxa de execução.
- KPIs estaduais e ranking de prefeituras na barra lateral.
- Aba 1 contendo listagem de emendas parlamentares associadas ao município ativo.
- Aba 2 contendo listagem cronológica de empenhos de obras públicas financiadas por recursos especiais.
- Aba 3 contendo o ranqueamento das principais empresas construtoras contratadas no município.
- Algoritmo Regex de vinculação automática de empenhos locais a emendas baseado nos códigos identificadores de 12 dígitos.
