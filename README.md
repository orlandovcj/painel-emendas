# Painel Interativo de Emendas Parlamentares, Obras e Materiais Permanentes em Santa Catarina (Emendas PIX)

Este é um painel de controle interativo e analítico premium, desenvolvido em Python com a biblioteca **Streamlit**, projetado para monitorar e fiscalizar a destinação e a execução física/financeira de recursos públicos federais provenientes de **Transferências Especiais da União (RP6 / Emendas PIX)** destinadas aos municípios do estado de Santa Catarina.

A aplicação cruza dados de repasses orçamentários, históricos de empenhos municipais para obras e materiais permanentes, licitações municipais enviadas ao tribunal, e consultas em tempo real com apuração de extratos e contas correntes na base oficial de dados do governo federal (Transferegov).

---

## 🎯 Utilidade e Objetivo

O painel visa aprimorar a transparência pública, permitindo que cidadãos, gestores municipais e órgãos de controle social e fiscalização (como o TCE-SC e a CGU):

- Visualizem a distribuição espacial dos recursos de emendas federais por meio de mapas interativos.
- Monitorem a eficiência de conversão financeira (relação entre o que foi empenhado/liquidado/pago nas prefeituras e os recursos PIX disponibilizados).
- Verifiquem o destino exato de cada pagamento feito por meio das contas específicas do governo federal, identificando fornecedores contratados e extratos de contas correntes ao vivo.
- Identifiquem indícios de desvios, inconsistências ou casamentos de licitações suspeitas através de algoritmos de similaridade textual de objetos.

---

## ⚡ Principais Funcionalidades

1. **Mapa de Distribuição Geográfica de Recursos**:
   Apresentação espacial de Santa Catarina com pontos georreferenciados para cada município beneficiário. O tamanho do círculo indica o volume financeiro recebido e a cor representa a eficiência de pagamento orçamentário.
2. **Filtro Avançado de Período (Multiselect)**:
   Barra lateral de controles com suporte para filtragem múltipla de anos (2022 a 2026), recalculando instantaneamente todos os gráficos, resumos estaduais, mapas e tabelas da interface.
3. **Indicador de Última Atualização**:
   Rastreamento dinâmico das planilhas de dados locais para exibir a data da última transação registrada em cada base (Emendas, Empenhos do TCE-SC e Licitações).
4. **Busca e Consulta em Tempo Real (Transferegov API)**:
   - Consulta viva pelo código da emenda e CNPJ do beneficiário municipal para retornar o plano de trabalho e objeto pactuado.
   - Consulta sequencial e paginada ao extrato financeiro da conta corrente oficial da emenda, acumulando todas as páginas de transações.
   - Padronização de documentos (CNPJ/CPF) com zeros à esquerda e formatação visual na listagem de movimentações.
5. **Gráfico de Concentração de Gastos (PJs)**:
   Exibição de um gráfico de barras horizontais com o total acumulado de débitos debitados da conta da emenda por fornecedor privado (Pessoa Jurídica) em ordem decrescente.
6. **Mecanismo de Similaridade Combinada com Ponderação Geográfica**:
   - Algoritmo de Jaccard Ponderado que realiza buscas de licitações municipais cadastradas que guardam similaridade com o objeto da emenda do Transferegov ou com o histórico de empenhos vinculados.
   - **Location Weight Boosting**: Palavras indicativas de vias públicas ou bairros (como nomes de ruas, avenidas, rodovias ou linhas) recebem peso extra ($4.0$) para evitar correspondências genéricas e focar na localização exata das intervenções urbanas.

---

## 📂 Organização das Abas (Tabs)

### 1. 📂 Emendas & Parlamentares

Focada nas fontes de recursos.

- Exibe a listagem de emendas parlamentares do município selecionado, o parlamentar autor do envio e os montantes correspondentes.
- Ao selecionar uma emenda, realiza a integração em tempo real com a API do governo federal apresentando o **Objeto Pactuado (API)** e dados de **Contas de Execução**.
- Contém a funcionalidade de consulta viva de **Lançamentos Financeiros (Extrato)** com cartões consolidados de crédito/débito e o gráfico analítico de pagamentos a PJs.
- Lista as **Licitações Municipais Associadas** por cálculo de similaridade textual, indicando o grau de correspondência e a origem do casamento.

### 2. 🚧 Empenhos de Obras e Mat. Permanentes

Focada na execução física e orçamentária dos contratos municipais.

- Apresenta uma tabela com os empenhos emitidos pela prefeitura que estão vinculados à emenda selecionada.
- Exibe as informações desmembradas de forma estruturada: número da licitação local correspondente, código do contrato, datas, credor fornecedor e valores de empenho, liquidação e pagamento.
- Inclui a coluna com a descrição textual do histórico do empenho municipal para maior auditoria.

### 3. 🏢 Empresas Contratadas

Focada nas construtoras e prestadoras de serviços terceirizadas.

- Exibe o ranking consolidado das empresas fornecedoras que receberam recursos no município selecionado.
- Detalha a quantidade de empenhos atribuídos a cada empresa, o total empenhado, liquidado e o efetivamente pago em conta corrente.

### 4. 📝 Detalhes e Histórico Textual

Focada na pesquisa textual e detalhamento individual de empenhos.

- Permite buscar empenhos e credores por palavras-chave específicas (ex: asfalto, creche, etc.).
- Apresenta os registros formatados em cartões informativos contendo o valor empenhado e pago.
- Oferece um botão para busca direta de informações do empenho no Google.
- Extrai e disponibiliza links clicáveis para acesso rápido a portais externos de transparência ou editais quando detectados no histórico.

---

## 🛠️ Estrutura do Projeto

```
painel-emendas/
├── dados/
│   ├── emendas-por-favorecido.csv                                      # Cadastro de emendas RP6 recebidas
│   ├── TCE_empenhos_obras_mat_permanentes_tranferencias_especiais.xlsx # Empenhos de obras e materiais permanentes de SC
│   ├── TCE_licitacoes_obras.xlsx                                       # Cadastro de licitações de obras de SC
│   └── municipios_sc.csv                                               # Coordenadas geográficas dos municípios de SC
├── app.py                                              # Script principal e código da interface Streamlit
├── requirements.txt                                    # Lista de dependências Python do projeto
├── LICENSE                                             # Licença do repositório
└── README.md                                           # Documentação oficial
```

---

## ⚙️ Requisitos e Instalação

### Requisitos Mínimos

- Python 3.9 ou superior instalado.
- Conexão ativa com a internet para as chamadas em tempo real da API do Transferegov.

### Instalação de Dependências

No console de comando (Terminal/PowerShell), clone este repositório ou navegue até a pasta do projeto e instale as bibliotecas requeridas executando:

```bash
pip install -r requirements.txt
```

As principais bibliotecas instaladas são:

- `streamlit`: Framework de desenvolvimento da interface web interativa.
- `pandas`: Processamento de bases de dados e manipulação de DataFrames.
- `openpyxl`: Suporte para leitura e gravação de arquivos planilhas Excel (`.xlsx`).
- `plotly`: Geração de gráficos interativos (barras, dispersão geográfico, mapas).
- `requests`: Comunicação HTTP para requisições de API externas.

### Executando o Painel

Para iniciar a aplicação localmente e visualizar no seu navegador web, rode o comando:

```bash
streamlit run app.py
```

O painel será aberto automaticamente no endereço padrão: [http://localhost:8501](http://localhost:8501).

---

## 📊 Fontes de Dados

- **Emendas Parlamentares RP6**: Portal de Dados Abertos do Transferegov (Ministério da Gestão e da Inovação em Serviços Públicos).
- **Empenhos de Obras e Materiais Permanentes (TCE-SC)**: Planilha `TCE_empenhos_obras_mat_permanentes_tranferencias_especiais.xlsx` extraída do **Portal Farol do TCE-SC**. Contém todos os empenhos dos municípios catarinenses que tiveram como fonte de recursos as Transferências Especiais da União (Emendas PIX) e foram aplicados em obras ou materiais permanentes.
- **Licitações Municipais de Santa Catarina**: Portal de Contas Públicas do Tribunal de Contas do Estado de Santa Catarina (TCE-SC).
- **Coordenadas de Municípios**: Diretoria de Geociências do Instituto Brasileiro de Geografia e Estatística (IBGE).

---

## ✍️ Autoria e Contato

- Desenvolvido por Orlando Castro.
- Parceria de programação assistida por Inteligência Artificial (Antigravity AI, Google DeepMind).
- Licenciado sob a Licença MIT. Para dúvidas ou sugestões de melhorias, entre em contato via canais do repositório.
