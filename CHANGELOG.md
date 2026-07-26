# Changelog

Todo o histórico de alterações deste projeto será documentado neste arquivo.

O formato é baseado no [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/) e este projeto segue a convenção de [Versionamento Semântico](https://semver.org/lang/pt-BR/).

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
