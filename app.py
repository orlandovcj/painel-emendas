import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import re
import unicodedata
import os
import urllib.parse
import requests

# Configuração da página do Streamlit
st.set_page_config(
    page_title="Painel de Emendas PIX - Obras e Materiais Permanentes em SC",
    page_icon="🇧🇷",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS para estilo premium (Aesthetics)
st.markdown("""
<style>
    /* Importando fonte do Google */
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');
    
    html, body, [data-testid="stSidebar"] {
        font-family: 'Outfit', sans-serif;
    }
    
    /* Efeito de Glassmorphism nos cards de métricas */
    .metric-card-custom {
        background: rgba(255, 255, 255, 0.9);
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        margin-bottom: 16px;
    }
    
    .metric-card-custom:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 20px rgba(0, 0, 0, 0.08);
        border-color: #cbd5e1;
    }
    
    /* Estilização para o título principal */
    .main-title {
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 50%, #10b981 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 2.5rem;
        margin-bottom: 0.5rem;
        text-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    
    /* Ajustes finos de Streamlit Elements */
    div[data-testid="stMetricValue"] {
        font-size: 2rem !important;
        font-weight: 700 !important;
    }
    
    button[data-baseweb="tab"] {
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        color: #475569 !important;
        padding: 12px 20px !important;
    }
    
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #2563eb !important;
        border-bottom-color: #2563eb !important;
    }
    
    /* Custom scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    ::-webkit-scrollbar-track {
        background: #f1f5f9;
    }
    ::-webkit-scrollbar-thumb {
        background: #cbd5e1;
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #94a3b8;
    }
</style>
""", unsafe_allow_html=True)

# Função auxiliar para normalização de nomes de municípios
def normalize_name(name):
    if not isinstance(name, str):
        return ""
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    name = name.upper().replace("'", " ").replace("-", " ")
    return " ".join(name.split())

# Correções ortográficas e discrepâncias de nomes de municípios entre emendas_sc e coordenadas
MUNI_CORRECTIONS = {
    'SAO LOURENCO D OESTE': 'SAO LOURENCO DO OESTE',
    'SAO MIGUEL D OESTE': 'SAO MIGUEL DO OESTE',
    'PRESIDENTE CASTELO BRANCO': 'PRESIDENTE CASTELLO BRANCO',
    'BALNEARIO DE PICARRAS': 'BALNEARIO PICARRAS'
}

def clean_muni_name(name):
    if not isinstance(name, str):
        return ""
    name_upper = name.strip().upper()
    for prefix in ["MUNICIPIO DE ", "MUNICIPIO DA ", "MUNICIPIO DO ", "MUNICIPIO "]:
        if name_upper.startswith(prefix):
            return name[len(prefix):].strip()
    return name.strip()

# Função para formatação amigável de valores monetários
def format_currency(value):
    if pd.isna(value) or value is None:
        return "R$ 0,00"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# Função auxiliar para extrair CNPJ puramente numérico da coluna Favorecido
def extract_cnpj(favorecido):
    if not isinstance(favorecido, str):
        return ""
    parts = favorecido.split(" - ")
    if len(parts) > 0:
        cnpj_raw = parts[0].strip()
        return "".join([c for c in cnpj_raw if c.isdigit()])
    return ""

# Função para consultar informações da emenda e executor na API do Transferegov
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_transferegov_data(emenda_code, cnpj_muni):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    url_plano = f"https://api.transferegov.gestao.gov.br/transferenciasespeciais/plano_acao_especial?cnpj_beneficiario_plano_acao=eq.{cnpj_muni}&numero_emenda_parlamentar_plano_acao=eq.{emenda_code}"

    
    try:
        r_plano = requests.get(url_plano, headers=headers, timeout=10)
        if r_plano.status_code == 200:
            data_plano = r_plano.json()
            if data_plano and len(data_plano) > 0:
                plano = data_plano[0]
                id_plano = plano.get("id_plano_acao")
                
                # Buscar dados do executor
                url_exec = f"https://api.transferegov.gestao.gov.br/transferenciasespeciais/executor_especial?id_plano_acao=eq.{id_plano}"
                r_exec = requests.get(url_exec, headers=headers, timeout=10)
                if r_exec.status_code == 200:
                    data_exec = r_exec.json()
                    if data_exec and len(data_exec) > 0:
                        executor = data_exec[0]
                        # Retornar as informações combinadas
                        return {
                            "id_plano_acao": id_plano,
                            "situacao": plano.get("situacao_plano_acao"),
                            "area_politica": plano.get("codigo_descricao_areas_politicas_publicas_plano_acao"),
                            "programa": plano.get("descricao_programacao_orcamentaria_plano_acao"),
                            "objeto": executor.get("objeto_executor"),
                            "banco_codigo": executor.get("codigo_banco_executor"),
                            "banco_nome": executor.get("nome_banco_executor"),
                            "agencia": executor.get("numero_agencia_executor"),
                            "agencia_dv": executor.get("dv_agencia_executor"),
                            "agencia_nome": executor.get("nome_agencia_executor"),
                            "conta": executor.get("numero_conta_executor"),
                            "conta_dv": executor.get("dv_conta_executor"),
                            "conta_especifica": executor.get("ind_recursos_gerenciados_conta_especifica_executor")
                        }
        return None
    except Exception as e:
        raise e

# Função para consultar lançamentos da conta bancária da emenda no Transferegov
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_financial_transfers(cnpj_muni, banco_codigo, agencia, conta):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    # Limpeza de parâmetros numéricos para evitar floats ou erros de formatação
    def clean_param(val):
        if val is None or pd.isna(val):
            return ""
        val_str = str(val).split('.')[0].strip()
        return "".join([c for c in val_str if c.isdigit()])
        
    cnpj_clean = clean_param(cnpj_muni)
    banco_clean = clean_param(banco_codigo)
    agencia_clean = clean_param(agencia)
    conta_clean = clean_param(conta)
    
    all_data = []
    page = 1
    total_pages = 1
    
    try:
        while page <= total_pages:
            url = f"https://api-publica.transferegov.gestao.gov.br/especiais/gestao_financeira_lancamentos_especiais?cnpj_ente_solicitante_gestao_financeira={cnpj_clean}&codigo_banco_gestao_financeira={banco_clean}&codigo_agencia_gestao_financeira={agencia_clean}&codigo_conta_gestao_financeira={conta_clean}&pagina={page}&tamanho_da_pagina=200"
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                res = r.json()
                if 'data' in res and res['data']:
                    all_data.extend(res['data'])
                # Atualizar total_pages na primeira resposta
                total_pages = res.get('total_pages', 1)
                page += 1
            else:
                break
                
        return {
            "data": all_data,
            "total_items": len(all_data),
            "total_pages": total_pages
        }
    except Exception as e:
        return None

# Função para limpar texto para comparação de similaridade
def clean_text_for_similarity(text):
    if not isinstance(text, str):
        return ""
    # Remover acentuação, converter para minúsculas e reter apenas alfanuméricos e espaços
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII').lower()
    text = "".join([c if c.isalnum() or c.isspace() else " " for c in text])
    return " ".join(text.split())

# Termos indicativos de locais e stopwords para ponderação
LOCATION_PREFIXES = {"rua", "avenida", "rodovia", "estrada", "bairro", "linha", "travessa", "beco", "sc", "br", "av", "tv", "loteamento", "praca", "praça", "distrito", "ruas", "avenidas", "linhas"}
STOPWORDS = {"de", "da", "do", "para", "com", "em", "a", "o", "e", "os", "as", "um", "uma", "no", "na", "nos", "nas"}

# Função para extrair pesos das palavras do texto
def get_word_weights(text):
    t_clean = clean_text_for_similarity(text)
    words = t_clean.split()
    
    # Identificar palavras que seguem termos indicativos de localização (nomes de ruas, bairros etc.)
    is_location = [False] * len(words)
    for i, w in enumerate(words):
        if w in LOCATION_PREFIXES:
            count = 0
            for j in range(i + 1, min(i + 4, len(words))):
                if words[j] in STOPWORDS:
                    continue
                if words[j] in LOCATION_PREFIXES:
                    break
                is_location[j] = True
                count += 1
                if count >= 2:  # Destacar até duas palavras principais do nome do local
                    break
                    
    weights = {}
    for i, w in enumerate(words):
        if is_location[i]:
            weights[w] = max(weights.get(w, 0.0), 4.0)  # Peso alto para nomes de ruas/bairros/rodovias
        elif w in STOPWORDS:
            weights[w] = max(weights.get(w, 0.0), 0.1)  # Peso muito baixo para stopwords
        elif w in LOCATION_PREFIXES:
            weights[w] = max(weights.get(w, 0.0), 1.5)  # Peso intermediário para os termos de localização
        else:
            weights[w] = max(weights.get(w, 0.0), 1.0)  # Peso padrão para palavras de conteúdo
            
    return weights

# Função para calcular similaridade de Jaccard ponderada (Weighted Jaccard / MinMax)
def calculate_similarity_jaccard(text1, text2):
    w1 = get_word_weights(text1)
    w2 = get_word_weights(text2)
    
    all_words = set(w1.keys()).union(set(w2.keys()))
    if not all_words:
        return 0.0
        
    num = 0.0
    den = 0.0
    for w in all_words:
        weight1 = w1.get(w, 0.0)
        weight2 = w2.get(w, 0.0)
        num += min(weight1, weight2)
        den += max(weight1, weight2)
        
    return num / den if den > 0 else 0.0

# Padrão Regex para extrair códigos de emendas de 12 dígitos que começam com '202'
EMENDA_PATTERN = re.compile(r'\b(202\d{9})\b')

# Função para carregar e cachear os dados
@st.cache_data(show_spinner="Carregando e processando os dados...")
def load_data():
    # base_dir = r"c:\Users\Dell\Documents\GitHub\painel-emendas\dados"
    base_dir = os.path.join(os.path.dirname(__file__), "dados")
    
    # Helper to clean bank account/code fields from CSV (floats to pure numeric strings)
    def clean_csv_int_str(val):
        if pd.isna(val) or val is None:
            return ""
        val_str = str(val).split('.')[0].strip()
        return "".join([c for c in val_str if c.isdigit()])
    
    # 1. Carregar CSV de Emendas
    df_emendas = pd.read_csv(os.path.join(base_dir, "emendas_sc.csv"), sep=";")
    
    # Criar colunas limpas
    df_emendas['municipio_orig'] = df_emendas['nome_municipio'].astype(str).apply(clean_muni_name)
    df_emendas['municipio_norm'] = df_emendas['municipio_orig'].apply(normalize_name).replace(MUNI_CORRECTIONS)
    df_emendas['valor_emenda'] = df_emendas['valor_emenda'].astype(float)
    
    # codigo_emenda is e.g. "202141850007-Jorginho Mello", extract the first 12 digits
    df_emendas['codigo_emenda'] = df_emendas['codigo_emenda'].astype(str).str.slice(0, 12).astype(int)
    
    # autor is e.g. "4185 - JORGINHO MELLO"
    df_emendas['autor'] = df_emendas['codigo_parlamentar'].astype(str) + " - " + df_emendas['nome_parlamentar'].astype(str).str.upper()
    
    # mes_ano is extracted from the 12-digit code's first 4 digits (year)
    df_emendas['year'] = df_emendas['codigo_emenda'].astype(str).str.slice(0, 4)
    df_emendas['mes_ano'] = "12/" + df_emendas['year']
    
    # cnpj_beneficiario is the cnpj_municipio padded to 14 digits
    df_emendas['cnpj_beneficiario'] = df_emendas['cnpj_municipio'].astype(str).str.zfill(14)
    
    # Clean bank account fields
    df_emendas['codigo_plano_acao'] = df_emendas['codigo_plano_acao'].fillna("").astype(str)
    df_emendas['objeto_emenda'] = df_emendas['objeto_emenda'].fillna("").astype(str)
    df_emendas['banco'] = df_emendas['banco'].fillna("").astype(str)
    df_emendas['codigo_banco'] = df_emendas['codigo_banco'].apply(clean_csv_int_str)
    df_emendas['agencia'] = df_emendas['agencia'].fillna("").astype(str)
    df_emendas['agencia_sem_dv'] = df_emendas['agencia_sem_dv'].apply(clean_csv_int_str)
    df_emendas['conta_corrente'] = df_emendas['conta_corrente'].fillna("").astype(str)
    df_emendas['conta_corrente_sem_dv'] = df_emendas['conta_corrente_sem_dv'].apply(clean_csv_int_str)
    
    df_emendas_clean = df_emendas[[
        'municipio_orig', 'municipio_norm', 'codigo_emenda', 'autor', 'valor_emenda', 'mes_ano', 'cnpj_beneficiario',
        'codigo_plano_acao', 'objeto_emenda', 'banco', 'codigo_banco', 'agencia', 'agencia_sem_dv', 'conta_corrente', 'conta_corrente_sem_dv'
    ]].copy()

    # 2. Carregar Excel do TCE-SC (Empenhos)
    df_tce = pd.read_excel(os.path.join(base_dir, "TCE_empenhos_obras_mat_permanentes_tranferencias_especiais.xlsx"))
    df_tce.columns = df_tce.columns.str.strip()
    
    # Mapear colunas do Excel para nomes limpos
    ente_col = 'Ente'
    emp_col = 'Valor Empenho'
    liq_col = [c for c in df_tce.columns if 'liqui' in c.lower()][0]
    pag_col = [c for c in df_tce.columns if 'pagam' in c.lower()][0]
    cred_col = [c for c in df_tce.columns if 'credor' in c.lower()][0]
    cnpj_col = [c for c in df_tce.columns if 'cnpj' in c.lower() or 'cpf' in c.lower()][0]
    hist_col = [c for c in df_tce.columns if 'hist' in c.lower()][0]
    num_emp_col = [c for c in df_tce.columns if 'empenho' in c.lower() and 'num' in c.lower()][0]
    ano_col = [c for c in df_tce.columns if 'ano' in c.lower()][0]
    lic_col = [c for c in df_tce.columns if 'licita' in c.lower() or 'contrato' in c.lower()][0]
    data_col = [c for c in df_tce.columns if 'data' in c.lower()][0]
    
    # Criar colunas limpas
    df_tce['municipio_norm'] = df_tce[ente_col].apply(normalize_name)
    df_tce['valor_empenhado'] = df_tce[emp_col].astype(float)
    df_tce['valor_liquidado'] = df_tce[liq_col].astype(float)
    df_tce['valor_pago'] = df_tce[pag_col].astype(float)
    df_tce['credor'] = df_tce[cred_col].astype(str)
    df_tce['cnpj_cpf'] = df_tce[cnpj_col].astype(str)
    df_tce['historico'] = df_tce[hist_col].astype(str)
    df_tce['num_empenho'] = df_tce[num_emp_col].astype(str)
    df_tce['ano_empenho'] = df_tce[ano_col].astype(int)
    df_tce['nr_licitacao'] = df_tce[lic_col].astype(str)
    
    # Converter data
    df_tce['data_empenho'] = pd.to_datetime(df_tce[data_col], errors='coerce').dt.strftime('%d/%m/%Y')
    
    df_tce_clean = df_tce[['Ente', 'municipio_norm', 'num_empenho', 'ano_empenho', 'data_empenho', 
                           'credor', 'cnpj_cpf', 'nr_licitacao', 'valor_empenhado', 
                           'valor_liquidado', 'valor_pago', 'historico']].copy()

    # 3. Carregar arquivo de coordenadas (municipios_sc.csv)
    df_coords = pd.read_csv(os.path.join(base_dir, "municipios_sc.csv"))
    
    # 4. Carregar Excel do TCE-SC (Licitações)
    df_lic = pd.read_excel(os.path.join(base_dir, "TCE_licitacoes_obras.xlsx"))
    df_lic.columns = df_lic.columns.str.strip()
    df_lic['municipio_norm'] = df_lic['Ente'].apply(normalize_name)
    
    # Extrair ano da licitação
    def extract_lic_year(row):
        edital = str(row['Número do Edital'])
        match = re.search(r'/(\d{4})\b', edital)
        if match:
            return int(match.group(1))
        for col_date in ['Data homologação', 'Data abertura certame', 'Data prevista publicação']:
            if col_date in row and pd.notna(row[col_date]):
                try:
                    return pd.to_datetime(row[col_date]).year
                except:
                    pass
        return 2024
        
    df_lic['ano_licitacao'] = df_lic.apply(extract_lic_year, axis=1)
    
    df_lic_clean = df_lic[['Ente', 'municipio_norm', 'Número do Edital', 'Modalidade', 
                           'Objeto Licitação', 'Valor previsto licitação', 
                           'Situação do Processo Licitatório', 'ano_licitacao']].copy()
    
    # 5. Vincular Empenhos a Emendas via Regex
    # Criamos um conjunto de códigos de emendas válidos por município
    emendas_por_muni = df_emendas_clean.groupby('municipio_norm')['codigo_emenda'].apply(set).to_dict()
    
    def link_row_to_emenda(row):
        text = str(row['historico']) + " " + str(row['nr_licitacao'])
        matches = EMENDA_PATTERN.findall(text)
        if matches:
            muni = row['municipio_norm']
            muni_valid_codes = emendas_por_muni.get(muni, set())
            for match in matches:
                code_int = int(match)
                if code_int in muni_valid_codes:
                    return code_int  # Retorna o primeiro código válido encontrado
        return None
    
    df_tce_clean['codigo_emenda'] = df_tce_clean.apply(link_row_to_emenda, axis=1)
    
    # 6. Calcular datas de última atualização
    # Emendas
    def parse_em_date(val):
        if not isinstance(val, str):
            return pd.NaT
        parts = val.split('/')
        if len(parts) == 2:
            return pd.to_datetime(f"01/{val}", format="%d/%m/%Y", errors='coerce')
        return pd.NaT
    max_emenda_date = df_emendas_clean['mes_ano'].apply(parse_em_date).max()
    max_emenda_str = max_emenda_date.strftime('%m/%Y') if pd.notna(max_emenda_date) else "N/A"
    
    # Empenhos
    max_empenho_date = pd.to_datetime(df_tce[data_col], errors='coerce').max()
    max_empenho_str = max_empenho_date.strftime('%d/%m/%Y') if pd.notna(max_empenho_date) else "N/A"
    
    # Licitações
    max_lic_date = pd.to_datetime(df_lic['Data Envio Licitação'], errors='coerce').max()
    max_lic_str = max_lic_date.strftime('%d/%m/%Y') if pd.notna(max_lic_date) else "N/A"

    
    metadata_dates = {
        "max_emenda": max_emenda_str,
        "max_empenho": max_empenho_str,
        "max_licitacao": max_lic_str
    }
    
    return df_emendas_clean, df_tce_clean, df_coords, df_lic_clean, metadata_dates

# Carregar dados
df_emendas, df_tce, df_coords, df_lic, metadata_dates = load_data()



# ----------------- INICIALIZAÇÃO DE ESTADO DA SESSÃO -----------------
if 'selected_mun' not in st.session_state:
    st.session_state.selected_mun = None

# Callback para quando a seleção do sidebar mudar
def on_sidebar_change():
    sel = st.session_state.sidebar_sel
    if sel == "Todos os Municípios":
        st.session_state.selected_mun = None
    else:
        st.session_state.selected_mun = sel

# ----------------- SIDEBAR DE CONTROLES -----------------
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/1/1a/Bandeira_de_Santa_Catarina.svg", width=120)
st.sidebar.markdown("<h2 style='margin-top: 10px;'>Filtros e Controles</h2>", unsafe_allow_html=True)

# Listagem de municípios ordenados para o selectbox
muni_list = ["Todos os Municípios"] + sorted(list(df_coords['nome'].unique()))

# Definir o índice padrão da sidebar com base na seleção ativa
sidebar_default_idx = 0
if st.session_state.selected_mun in muni_list:
    sidebar_default_idx = muni_list.index(st.session_state.selected_mun)

selected_muni = st.sidebar.selectbox(
    "Selecione um município no mapa ou abaixo:",
    muni_list,
    index=sidebar_default_idx,
    key="sidebar_sel",
    on_change=on_sidebar_change
)

# Filtro por Ano na Sidebar (Multiselect para múltiplos anos/períodos)
st.sidebar.markdown("---")
st.sidebar.subheader("📅 Período / Anos de Referência")
years_options = sorted(list(set(df_emendas['mes_ano'].str.split('/').str[-1].dropna().unique())), reverse=True)
selected_years = st.sidebar.multiselect(
    "Selecione os anos para exibir no painel:",
    options=years_options,
    default=years_options,
    key="selected_years_filter"
)

if not selected_years:
    st.sidebar.warning("⚠️ Nenhum ano selecionado. Exibindo todos por padrão.")
    active_years = years_options
else:
    active_years = selected_years

# Aplicar o filtro de ano por sombreamento de variáveis
df_emendas = df_emendas[df_emendas['mes_ano'].str.split('/').str[-1].isin(active_years)].copy()
df_tce = df_tce[df_tce['ano_empenho'].astype(str).isin(active_years)].copy()
df_lic = df_lic[df_lic['ano_licitacao'].astype(str).isin(active_years)].copy()

# Estatísticas Rápidas Estaduais na Sidebar (dinâmicas com os anos selecionados)
st.sidebar.markdown("---")
if len(active_years) == len(years_options):
    years_label = "Todos"
elif len(active_years) == 1:
    years_label = str(active_years[0])
else:
    years_label = ", ".join(sorted(active_years))
st.sidebar.markdown(f"### Resumo do Estado ({years_label})")
total_emendas_est = df_emendas['valor_emenda'].sum()
total_empenhado_est = df_tce['valor_empenhado'].sum()
total_pago_est = df_tce['valor_pago'].sum()

st.sidebar.metric("Total de Emendas PIX", format_currency(total_emendas_est))
st.sidebar.metric("Total Empenhado (Obras e Mat. Permanentes)", format_currency(total_empenhado_est))
st.sidebar.metric("Total Pago (Obras e Mat. Permanentes)", format_currency(total_pago_est))
if total_emendas_est > 0:
    st.sidebar.markdown(f"**Taxa de Execução Geral:** {(total_pago_est / total_emendas_est * 100):.1f}%")
else:
    st.sidebar.markdown("**Taxa de Execução Geral:** N/A")

# Botão para limpar a seleção
if st.sidebar.button("Resetar Seleção", type="primary"):
    st.session_state.selected_mun = None
    st.rerun()

# Informação de última atualização dos dados
st.sidebar.markdown("---")
st.sidebar.markdown("### 🔄 Última Atualização")
st.sidebar.markdown(f"""
<div style="
    font-size: 0.8rem; 
    color: #475569; 
    line-height: 1.6; 
    background-color: #f1f5f9; 
    padding: 12px; 
    border-radius: 10px; 
    border: 1px solid #cbd5e1;
">
    <div>📅 <strong>Emendas:</strong> {metadata_dates['max_emenda']}</div>
    <div>🏗️ <strong>Empenhos:</strong> {metadata_dates['max_empenho']}</div>
    <div>🔍 <strong>Licitações:</strong> {metadata_dates['max_licitacao']}</div>
</div>
""", unsafe_allow_html=True)

# ----------------- ESTRUTURAÇÃO DO MAPA AGREGADO -----------------
# Agrupar Emendas (CSV) por Município
df_emendas_agg = df_emendas.groupby('municipio_norm').agg(
    total_emendas=('valor_emenda', 'sum'),
    qtd_emendas=('codigo_emenda', 'count'),
    parlamentares=('autor', lambda x: ", ".join(x.str.split(" - ").str[-1].unique()))
).reset_index()

# Agrupar Empenhos (Excel) por Município
df_tce_agg = df_tce.groupby('municipio_norm').agg(
    total_empenhado=('valor_empenhado', 'sum'),
    total_liquidado=('valor_liquidado', 'sum'),
    total_pago=('valor_pago', 'sum'),
    qtd_empenhos=('num_empenho', 'count'),
    qtd_empresas=('cnpj_cpf', 'nunique')
).reset_index()

# Merge dos dados agregados com a base de coordenadas do IBGE
df_map_agg = df_coords.merge(df_emendas_agg, left_on='nome_normalizado', right_on='municipio_norm', how='left')
df_map_agg = df_map_agg.merge(df_tce_agg, on='municipio_norm', how='left')

# Preencher NAs com 0 nas colunas monetárias e de contagem
fill_cols = ['total_emendas', 'qtd_emendas', 'total_empenhado', 'total_liquidado', 'total_pago', 'qtd_empenhos', 'qtd_empresas']
df_map_agg[fill_cols] = df_map_agg[fill_cols].fillna(0)
df_map_agg['parlamentares'] = df_map_agg['parlamentares'].fillna("Nenhum identificado")

# Calcular taxa de execução local (Pago / Recebido)
df_map_agg['Execução (%)'] = (df_map_agg['total_pago'] / df_map_agg['total_emendas'] * 100).fillna(0).clip(0, 100)

# Criar coluna para exibição customizada no hover do Plotly
def get_hover_text(row):
    return (
        f"<b>{row['nome']}</b><br>"
        f"Emendas Recebidas: {format_currency(row['total_emendas'])} ({int(row['qtd_emendas'])} emendas)<br>"
        f"Pago para Obras e Mat. Permanentes: {format_currency(row['total_pago'])} ({int(row['qtd_empenhos'])} empenhos)<br>"
        f"Empresas Contratadas: {int(row['qtd_empresas'])}<br>"
        f"Taxa de Execução: {row['Execução (%)']:.1f}%<br>"
        f"Parlamentares: {row['parlamentares']}"
    )
df_map_agg['hover_text'] = df_map_agg.apply(get_hover_text, axis=1)

# Ajustar tamanho visual das bolhas para que mesmo municípios sem emendas tenham um ponto clicável
df_map_agg['Tamanho Visual'] = df_map_agg['total_emendas'].apply(lambda x: max(x, 150000) if x > 0 else 60000)

# ----------------- RENDERIZAÇÃO DA INTERFACE PRINCIPAL -----------------

st.markdown("<h1 class='main-title'>Painel Interativo de Emendas PIX (RP6) - Santa Catarina</h1>", unsafe_allow_html=True)
st.markdown("<div style='font-size: 0.85rem; color: #64748b; margin-top: -15px; margin-bottom: 15px; font-weight: 500;'>Versão 1.5.0</div>", unsafe_allow_html=True)
st.markdown("##### Cruzamento de dados de Transferências Especiais da União (Emendas PIX), Obras e Mat. Permanentes (TCE-SC).")

# Se nenhum município estiver selecionado, exibir o mapa geral e estatísticas globais do estado
if st.session_state.selected_mun is None:
    st.markdown("---")
    col1, col2 = st.columns([7, 3])
    
    with col1:
        st.subheader("Mapa Interativo de Santa Catarina")
        st.caption("DICA: Clique em um ponto no mapa para abrir o painel detalhado do município. Passe o mouse para ver resumos.")
        
        # Configurar mapa do Plotly Express
        fig = px.scatter_map(
            df_map_agg,
            lat="latitude",
            lon="longitude",
            size="Tamanho Visual",
            color="Execução (%)",
            color_continuous_scale=px.colors.sequential.Viridis,
            range_color=[0, 100],
            hover_name="nome",
            hover_data={"latitude": False, "longitude": False, "Tamanho Visual": False, "Execução (%)": False},
            zoom=6.8,
            center={"lat": -27.25, "lon": -50.25},
            height=600,
        )
        
        # Inserir hover customizado e estilização do mapa
        fig.update_traces(
            text=df_map_agg['hover_text'],
            hovertemplate="%{text}<extra></extra>",
            marker=dict(opacity=0.85)
        )
        
        fig.update_layout(
            map_style="open-street-map",
            margin={"r":0,"t":0,"l":0,"b":0},
            coloraxis_colorbar=dict(
                title="Taxa de Execução (%)",
                thicknessmode="pixels", thickness=15,
                lenmode="pixels", len=300,
                yanchor="top", y=1,
                xanchor="left", x=0.02
            )
        )
        
        # Renderizar o gráfico com eventos de seleção/clique ativos
        map_event = st.plotly_chart(fig, on_select="rerun", key="sc_map_chart", width="stretch")
        
        # Tratar o evento de clique/seleção no mapa
        if map_event and "selection" in map_event and "points" in map_event["selection"] and len(map_event["selection"]["points"]) > 0:
            pt = map_event["selection"]["points"][0]
            selected_idx = pt["point_index"]
            clicked_muni_name = df_map_agg.iloc[selected_idx]['nome']
            
            # Atualiza o estado e recarrega
            st.session_state.selected_mun = clicked_muni_name
            st.rerun()
            
    with col2:
        st.subheader("Estatísticas e Rankings do Estado")
        
        # Métricas em HTML customizado (Aesthetics)
        st.markdown(f"""
        <div class="metric-card-custom" style="border-left: 5px solid #2563eb;">
            <div style="font-size: 0.85rem; color: #64748b; font-weight: 600; text-transform: uppercase;">Emendas PIX Recebidas (Total)</div>
            <div style="font-size: 2rem; font-weight: 800; color: #1e3a8a; margin-top: 4px;">{format_currency(total_emendas_est)}</div>
            <div style="font-size: 0.8rem; color: #475569; margin-top: 6px;">
                Total de emendas enviadas aos 294 municípios de SC através do tipo RP6.
            </div>
        </div>
        
        <div class="metric-card-custom" style="border-left: 5px solid #10b981;">
            <div style="font-size: 0.85rem; color: #64748b; font-weight: 600; text-transform: uppercase;">Total Pago em Obras e Mat. Permanentes</div>
            <div style="font-size: 2rem; font-weight: 800; color: #065f46; margin-top: 4px;">{format_currency(total_pago_est)}</div>
            <div style="font-size: 0.8rem; color: #475569; margin-top: 6px;">
                Soma de pagamentos efetuados pelos municípios para fornecedores de obras e material permanente contratadas.
            </div>
        </div>
        
        <div class="metric-card-custom" style="border-left: 5px solid #f59e0b;">
            <div style="font-size: 0.85rem; color: #64748b; font-weight: 600; text-transform: uppercase;">Percentual de Execução</div>
            <div style="font-size: 2rem; font-weight: 800; color: #92400e; margin-top: 4px;">{(total_pago_est / total_emendas_est * 100):.2f}%</div>
            <div style="font-size: 0.8rem; color: #475569; margin-top: 6px;">
                Indica o quanto do recurso de transferências especiais de emendas já foi pago nas obras e material permanente contratadas.
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown("---")
    st.subheader("Análise Geral de Recursos e Parlamentares")
    col_c1, col_c2 = st.columns(2)
    
    with col_c1:
        # Top 10 Municípios Recebedores de Emendas PIX
        df_top_mun = df_map_agg.nlargest(10, 'total_emendas')
        fig_mun = px.bar(
            df_top_mun,
            x="total_emendas",
            y="nome",
            orientation="h",
            title="Top 10 Municípios por Recebimento de Emendas PIX (R$)",
            labels={"total_emendas": "Total de Emendas (R$)", "nome": "Município"},
            color="total_emendas",
            color_continuous_scale=px.colors.sequential.Blues
        )
        fig_mun.update_layout(yaxis={'categoryorder':'total ascending'}, showlegend=False, coloraxis_showscale=False)
        st.plotly_chart(fig_mun, width="stretch")
        
    with col_c2:
        # Top 10 Parlamentares por Valor de Emenda em SC
        df_top_aut = df_emendas.groupby('autor')['valor_emenda'].sum().reset_index().nlargest(10, 'valor_emenda')
        # Limpar nome do parlamentar para o gráfico
        df_top_aut['Parlamentar'] = df_top_aut['autor'].str.split(" - ").str[-1]
        fig_aut = px.bar(
            df_top_aut,
            x="valor_emenda",
            y="Parlamentar",
            orientation="h",
            title="Top 10 Autores por Total de Emendas Destinadas a SC (R$)",
            labels={"valor_emenda": "Total Destinado (R$)", "Parlamentar": "Parlamentar"},
            color="valor_emenda",
            color_continuous_scale=px.colors.sequential.Greens
        )
        fig_aut.update_layout(yaxis={'categoryorder':'total ascending'}, showlegend=False, coloraxis_showscale=False)
        st.plotly_chart(fig_aut, width="stretch")

# Se um município específico estiver selecionado
else:
    # Obter dados consolidados do município selecionado
    muni_name = st.session_state.selected_mun
    muni_norm = normalize_name(muni_name)
    
    # Obter linha agregada no mapa
    muni_map_data = df_map_agg[df_map_agg['nome_normalizado'] == muni_norm]
    
    if muni_map_data.empty:
        st.error(f"Município {muni_name} não encontrado nas bases de dados.")
        st.session_state.selected_mun = None
        st.button("Voltar ao mapa geral")
    else:
        muni_row = muni_map_data.iloc[0]
        
        # Filtros locais de dados
        muni_emendas_df = df_emendas[df_emendas['municipio_norm'] == muni_norm].copy()
        muni_tce_df = df_tce[df_tce['municipio_norm'] == muni_norm].copy()
        
        # Título da Seção do Município
        st.markdown("---")
        st.markdown(f"<h2 style='color:#1e3a8a; margin-top:0px;'>📍 Painel de Controle: {muni_name}</h2>", unsafe_allow_html=True)
        
        # Botão rápido para retornar ao mapa geral
        if st.button("⬅️ Voltar ao Mapa Geral de SC"):
            st.session_state.selected_mun = None
            st.rerun()
            
        # Cartões de Métricas Locais (Aesthetics)
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        
        # 1. Total Emendas
        with col_m1:
            st.markdown(f"""
            <div class="metric-card-custom" style="border-left: 4px solid #3b82f6;">
                <div style="font-size: 0.8rem; color: #64748b; font-weight: 600; text-transform: uppercase;">Emendas PIX Recebidas</div>
                <div style="font-size: 1.6rem; font-weight: 700; color: #1e3a8a; margin-top: 4px;">{format_currency(muni_row['total_emendas'])}</div>
                <div style="font-size: 0.85rem; color: #475569; margin-top: 6px;"><b>{int(muni_row['qtd_emendas'])}</b> emendas destinadas</div>
            </div>
            """, unsafe_allow_html=True)
            
        # 2. Total Empenhado para Obras e Materiais Permanentes
        with col_m2:
            st.markdown(f"""
            <div class="metric-card-custom" style="border-left: 4px solid #f59e0b;">
                <div style="font-size: 0.8rem; color: #64748b; font-weight: 600; text-transform: uppercase;">Total Empenhado (Obras e Mat. Perm.)</div>
                <div style="font-size: 1.6rem; font-weight: 700; color: #b45309; margin-top: 4px;">{format_currency(muni_row['total_empenhado'])}</div>
                <div style="font-size: 0.85rem; color: #475569; margin-top: 6px;"><b>{int(muni_row['qtd_empenhos'])}</b> empenhos registrados</div>
            </div>
            """, unsafe_allow_html=True)
            
        # 3. Total Pago para Obras e Materiais Permanentes
        with col_m3:
            st.markdown(f"""
            <div class="metric-card-custom" style="border-left: 4px solid #10b981;">
                <div style="font-size: 0.8rem; color: #64748b; font-weight: 600; text-transform: uppercase;">Total Pago em Obras e Mat. Perm.</div>
                <div style="font-size: 1.6rem; font-weight: 700; color: #047857; margin-top: 4px;">{format_currency(muni_row['total_pago'])}</div>
                <div style="font-size: 0.85rem; color: #475569; margin-top: 6px;">Liquidado: {format_currency(muni_row['total_liquidado'])}</div>
            </div>
            """, unsafe_allow_html=True)
            
        # 4. Percentual de Execução Local
        with col_m4:
            local_exec = muni_row['Execução (%)']
            st.markdown(f"""
            <div class="metric-card-custom" style="border-left: 4px solid #8b5cf6;">
                <div style="font-size: 0.8rem; color: #64748b; font-weight: 600; text-transform: uppercase;">Percentual de Execução</div>
                <div style="font-size: 1.6rem; font-weight: 700; color: #6d28d9; margin-top: 4px;">{local_exec:.1f}%</div>
                <div style="font-size: 0.85rem; color: #475569; margin-top: 6px;">Saldo: {format_currency(max(0, muni_row['total_emendas'] - muni_row['total_pago']))}</div>
            </div>
            """, unsafe_allow_html=True)
            
        # Abas de navegação de dados do município
        tab_emendas, tab_obras, tab_empresas, tab_historico = st.tabs([
            "📂 Emendas & Parlamentares",
            "🚧 Empenhos de Obras e Mat. Permanentes",
            "🏢 Empresas Contratadas",
            "📝 Detalhes e Histórico Textual"
        ])
        
        # ----------------- ABA 1: EMENDAS E PARLAMENTARES -----------------
        with tab_emendas:
            st.subheader("Lista de Emendas Especiais Recebidas")
            if muni_emendas_df.empty:
                st.info("Nenhuma emenda especial identificada para este município na base de emendas.")
            else:
                # Exibir tabela formatada de emendas
                df_em_show = muni_emendas_df[['codigo_emenda', 'autor', 'mes_ano', 'valor_emenda']].copy()
                df_em_show.columns = ['Código da Emenda', 'Autor/Parlamentar', 'Mês/Ano', 'Valor (R$)']
                df_em_show['Valor (R$)'] = df_em_show['Valor (R$)'].apply(format_currency)
                
                col_tab1_1, col_tab1_2 = st.columns([6, 4])
                
                with col_tab1_1:
                    # Habilita seleção de linha simples na tabela de emendas
                    selection = st.dataframe(
                        df_em_show,
                        width="stretch",
                        hide_index=True,
                        on_select="rerun",
                        selection_mode="single-row",
                        key=f"emendas_table_{muni_norm}"
                    )
                
                with col_tab1_2:
                    # Gráfico de pizza de divisão por autor
                    df_pie = muni_emendas_df.groupby('autor')['valor_emenda'].sum().reset_index()
                    df_pie['Parlamentar'] = df_pie['autor'].str.split(" - ").str[-1]
                    fig_pie = px.pie(
                        df_pie,
                        values='valor_emenda',
                        names='Parlamentar',
                        title='Distribuição dos Recursos por Parlamentar',
                        hole=0.4
                    )
                    fig_pie.update_layout(showlegend=True)
                    st.plotly_chart(fig_pie, width="stretch")
                
                # Exibir detalhes da emenda selecionada vindos da API Transferegov
                selected_rows = selection.get("selection", {}).get("rows", [])
                if selected_rows:
                    row_idx = selected_rows[0]
                    # Obter código e CNPJ do DataFrame de emendas original do município
                    row_data = muni_emendas_df.iloc[row_idx]
                    selected_code = row_data['codigo_emenda']
                    selected_cnpj = row_data['cnpj_beneficiario']
                    selected_autor = row_data['autor']
                    
                    # Obter dados offline
                    offline_plano_acao = row_data.get('codigo_plano_acao', '')
                    offline_objeto = row_data.get('objeto_emenda', '')
                    offline_banco_nome = row_data.get('banco', '')
                    offline_banco_codigo = row_data.get('codigo_banco', '')
                    offline_agencia = row_data.get('agencia', '')
                    offline_agencia_sem_dv = row_data.get('agencia_sem_dv', '')
                    offline_conta = row_data.get('conta_corrente', '')
                    offline_conta_sem_dv = row_data.get('conta_corrente_sem_dv', '')
                    
                    st.markdown("---")
                    st.markdown(f"#### 🔍 Dados Detalhados da Emenda: **{selected_code}** ({selected_autor.split(' - ')[-1]})")
                    
                    # Tentamos enriquecer com a API em tempo real
                    api_data = None
                    try:
                        # Buscar dados da API com cache passando o CNPJ e código
                        api_data = fetch_transferegov_data(selected_code, selected_cnpj)
                    except Exception as e:
                        pass
                    
                    # Combinar dados (API tem prioridade para valores dinâmicos)
                    objeto = api_data.get('objeto') if (api_data and api_data.get('objeto')) else (offline_objeto if offline_objeto else "Objeto não informado no cadastro offline.")
                    area_politica = api_data.get('area_politica', 'Área pública não disponível offline') if api_data else 'Área pública não disponível offline'
                    programa = api_data.get('programa', 'Programa não disponível offline') if api_data else 'Programa não disponível offline'
                    
                    banco_codigo = api_data.get('banco_codigo') if (api_data and api_data.get('banco_codigo')) else offline_banco_codigo
                    banco_nome = api_data.get('banco_nome') if (api_data and api_data.get('banco_nome')) else offline_banco_nome
                    
                    if api_data:
                        agencia_completa = f"{api_data['agencia']}-{api_data['agencia_dv']}" if api_data.get('agencia_dv') else api_data['agencia']
                        agencia_nome = f" ({api_data['agencia_nome']})" if api_data.get('agencia_nome') else ""
                        agencia_display = f"{agencia_completa}{agencia_nome}"
                        conta_display = f"C/C: {api_data['conta']}-{api_data['conta_dv']}"
                        
                        agencia_para_extrato = api_data['agencia']
                        conta_para_extrato = api_data['conta']
                        
                        situacao = api_data.get('situacao', 'N/A')
                        id_plano_acao = api_data.get('id_plano_acao', offline_plano_acao)
                        conta_especifica = api_data.get('conta_especifica', 'Não Identificado')
                    else:
                        agencia_display = offline_agencia if offline_agencia else "Não informada"
                        conta_display = f"C/C: {offline_conta}" if offline_conta else "C/C: Não informada"
                        
                        agencia_para_extrato = offline_agencia_sem_dv
                        conta_para_extrato = offline_conta_sem_dv
                        
                        situacao = "Disponível apenas online"
                        id_plano_acao = offline_plano_acao
                        conta_especifica = "Não Identificado"
                        
                    col_api1, col_api2 = st.columns([6, 4])
                    
                    with col_api1:
                        # Caixa de destaque para o Objeto Pactuado
                        st.markdown(f"""
                        <div style="background-color: #eff6ff; border: 1px solid #bfdbfe; border-radius: 12px; padding: 16px; margin-bottom: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.01);">
                            <div style="font-weight: 700; color: #1e40af; margin-bottom: 6px; font-size: 0.95rem; text-transform: uppercase; letter-spacing: 0.5px;">🎯 Objeto Pactuado</div>
                            <div style="font-size: 1rem; color: #1e3a8a; font-style: italic; line-height: 1.5;">
                                "{objeto}"
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Detalhes do Plano
                        st.markdown(f"""
                        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 12px 16px; font-size: 0.9rem; color: #475569; box-shadow: 0 2px 4px rgba(0,0,0,0.01);">
                            <div style="margin-bottom: 6px;"><strong>Área de Política Pública:</strong> {area_politica}</div>
                            <div><strong>Programa Orçamentário:</strong> {programa}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if api_data is None:
                            st.caption("⚠️ Não foi possível obter dados em tempo real da API do Transferegov. Exibindo dados offline.")
                        
                    with col_api2:
                        # Cartão bancário estilizado
                        if conta_especifica == "Sim":
                            especifica_badge = '<span style="background-color: #d1fae5; color: #065f46; padding: 4px 10px; border-radius: 9999px; font-size: 0.75rem; font-weight: 700; border: 1px solid #a7f3d0;">CONTA ESPECÍFICA</span>'
                        elif conta_especifica == "Não":
                            especifica_badge = '<span style="background-color: #ffedd5; color: #9a3412; padding: 4px 10px; border-radius: 9999px; font-size: 0.75rem; font-weight: 700; border: 1px solid #fed7aa;">CONTA COMUM</span>'
                        else:
                            especifica_badge = '<span style="background-color: #f1f5f9; color: #475569; padding: 4px 10px; border-radius: 9999px; font-size: 0.75rem; font-weight: 700; border: 1px solid #cbd5e1;">CADASTRADA</span>'
                        
                        st.markdown(f"""
                        <div style="
                            background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
                            color: #f8fafc;
                            border-radius: 16px;
                            padding: 20px;
                            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
                            border: 1px solid #475569;
                        ">
                            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #475569; padding-bottom: 10px; margin-bottom: 12px;">
                                <span style="font-weight: 700; font-size: 0.9rem; letter-spacing: 0.5px; color: #94a3b8;">💳 CONTAS DE EXECUÇÃO</span>
                                {especifica_badge}
                            </div>
                            <div style="font-size: 0.85rem; color: #cbd5e1; margin-bottom: 8px;">
                                <strong>Banco:</strong> {banco_codigo} - {banco_nome}
                            </div>
                            <div style="font-size: 0.85rem; color: #cbd5e1; margin-bottom: 8px;">
                                <strong>Agência:</strong> {agencia_display}
                            </div>
                            <div style="font-size: 1.15rem; font-weight: 700; margin-top: 12px; font-family: monospace; letter-spacing: 1px; color: #60a5fa;">
                                {conta_display}
                            </div>
                            <div style="font-size: 0.75rem; color: #94a3b8; margin-top: 15px; text-align: right;">
                                Situação do Plano: <b>{situacao}</b> {f"(ID: {id_plano_acao})" if id_plano_acao else ""}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                    
                    # --- SEÇÃO DE LANÇAMENTOS FINANCEIROS (EXTRATO) ---
                    pjs_paid_cnpjs = set()
                    fin_data = None
                    if banco_codigo and agencia_para_extrato and conta_para_extrato:
                        with st.spinner("Carregando lançamentos financeiros..."):
                            fin_data = fetch_financial_transfers(
                                selected_cnpj,
                                banco_codigo,
                                agencia_para_extrato,
                                conta_para_extrato
                            )
                            
                    if fin_data and 'data' in fin_data and fin_data['data']:
                        st.markdown("<br>", unsafe_allow_html=True)
                        st.markdown("##### 💸 Movimentações Financeiras da Conta Corrente (Transferegov API)")
                        
                        tx_list = fin_data['data']
                        
                        # Calcular resumos
                        total_creditos = sum([tx['valor_gestao_financeira'] for tx in tx_list if tx['tipo_operacao_gestao_financeira'] == 'C'])
                        total_debitos = sum([tx['valor_gestao_financeira'] for tx in tx_list if tx['tipo_operacao_gestao_financeira'] == 'D'])
                        saldo_final = total_creditos - total_debitos
                        
                        # Renderizar KPIs consolidados
                        col_k1, col_k2, col_k3 = st.columns(3)
                        with col_k1:
                            st.markdown(f"""
                            <div style="background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 12px; padding: 15px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.01);">
                                <div style="font-size: 0.72rem; color: #15803d; font-weight: 700; text-transform: uppercase; letter-spacing: 0.3px;">Total Recebido (Créditos)</div>
                                <div style="font-size: 1.2rem; font-weight: 700; color: #166534; margin-top: 5px;">{format_currency(total_creditos)}</div>
                            </div>
                            """, unsafe_allow_html=True)
                        with col_k2:
                            st.markdown(f"""
                            <div style="background-color: #fef2f2; border: 1px solid #fecaca; border-radius: 12px; padding: 15px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.01);">
                                <div style="font-size: 0.72rem; color: #b91c1c; font-weight: 700; text-transform: uppercase; letter-spacing: 0.3px;">Total Retirado (Débitos)</div>
                                <div style="font-size: 1.2rem; font-weight: 700; color: #991b1b; margin-top: 5px;">{format_currency(total_debitos)}</div>
                            </div>
                            """, unsafe_allow_html=True)
                        with col_k3:
                            bg_color = "#f0fdfa" if saldo_final >= 0 else "#fff7ed"
                            border_color = "#99f6e4" if saldo_final >= 0 else "#ffedd5"
                            text_color = "#115e59" if saldo_final >= 0 else "#9a3412"
                            st.markdown(f"""
                            <div style="background-color: {bg_color}; border: 1px solid {border_color}; border-radius: 12px; padding: 15px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.01);">
                                <div style="font-size: 0.72rem; color: {text_color}; font-weight: 700; text-transform: uppercase; letter-spacing: 0.3px;">Saldo da Conta</div>
                                <div style="font-size: 1.2rem; font-weight: 700; color: {text_color}; margin-top: 5px;">{format_currency(saldo_final)}</div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                        st.markdown("<br>", unsafe_allow_html=True)
                        
                        # Criar dataframe para exibição
                        df_tx = pd.DataFrame(tx_list)
                        df_tx_show = pd.DataFrame()
                        
                        df_tx_show['Data'] = pd.to_datetime(df_tx['data_lancamento_gestao_financeira']).dt.strftime('%d/%m/%Y')
                        df_tx_show['Operação'] = df_tx['tipo_operacao_gestao_financeira'].apply(
                            lambda x: "🟢 Crédito" if x == 'C' else "🔴 Débito"
                        )
                        df_tx_show['Descrição'] = df_tx['descricao_gestao_financeira'].fillna("Lançamento")
                        
                        def get_agent_and_doc(row):
                            if row['tipo_operacao_gestao_financeira'] == 'C':
                                agent = row['nome_depositante_gestao_financeira']
                                doc = row['doc_depositante_gestao_financeira']
                            else:
                                agent = row['nome_favorecido_gestao_financeira']
                                doc = row['doc_favorecido_gestao_financeira']
                            
                            # Obter apenas dígitos numéricos para o documento
                            doc_str = ""
                            if pd.notna(doc):
                                doc_str = "".join([c for c in str(doc).split('.')[0] if c.isdigit()])
                                
                            # Padronizar CNPJ (14 dígitos) e CPF (11 dígitos) com preenchimento de zeros à esquerda se suprimidos
                            if 11 < len(doc_str) <= 14:
                                doc_str = doc_str.zfill(14)
                                formatted = f"{doc_str[:2]}.{doc_str[2:5]}.{doc_str[5:8]}/{doc_str[8:12]}-{doc_str[12:]}"
                            elif 0 < len(doc_str) <= 11:
                                doc_str = doc_str.zfill(11)
                                formatted = f"{doc_str[:3]}.{doc_str[3:6]}.{doc_str[6:9]}-{doc_str[9:]}"
                            else:
                                formatted = "-"
                                
                            agent_str = "Não Identificado"
                            if pd.notna(agent):
                                agent_str = str(agent).strip()
                                if agent_str.lower() in ("nan", "none", ""):
                                    agent_str = "Não Identificado"
                                    
                            return pd.Series([agent_str, formatted])
                            
                        df_tx_show[['Origem/Destino', 'CNPJ/CPF']] = df_tx.apply(get_agent_and_doc, axis=1)
                        df_tx_show['Valor'] = df_tx['valor_gestao_financeira'].apply(format_currency)
                        df_tx_show = df_tx_show.sort_values(by='Data', ascending=False)
                        
                        st.dataframe(
                            df_tx_show[['Data', 'Operação', 'Descrição', 'Origem/Destino', 'CNPJ/CPF', 'Valor']],
                            width="stretch",
                            hide_index=True
                        )
                        
                        # --- GRÁFICO DE BARRAS HORIZONTAIS: DÉBITOS DESTINADOS A PJs ---
                        def is_pj_debit(row):
                            if row.get('tipo_operacao_gestao_financeira') != 'D':
                                return False
                            doc = row.get('doc_favorecido_gestao_financeira')
                            doc_str = ""
                            if pd.notna(doc):
                                doc_str = "".join([c for c in str(doc).split('.')[0] if c.isdigit()])
                                # Tratar supressão de zeros à esquerda para CNPJ
                                if 11 < len(doc_str) <= 14:
                                    doc_str = doc_str.zfill(14)
                                    
                            tipo = row.get('tipo_favorecido_gestao_financeira')
                            is_pj = (str(tipo) in ('2', '2.0')) or (len(doc_str) == 14)
                            
                            fav = row.get('nome_favorecido_gestao_financeira')
                            has_fav = pd.notna(fav) and str(fav).strip() != "" and str(fav).strip().lower() not in ("nan", "none")
                            return is_pj and has_fav

                        df_pj_debits = df_tx[df_tx.apply(is_pj_debit, axis=1)].copy()
                        for doc in df_pj_debits['doc_favorecido_gestao_financeira'].dropna():
                            doc_str = "".join([c for c in str(doc).split('.')[0] if c.isdigit()])
                            if len(doc_str) > 11:
                                pjs_paid_cnpjs.add(doc_str.zfill(14))
                            elif len(doc_str) > 0:
                                pjs_paid_cnpjs.add(doc_str.zfill(11))
                        
                        if not df_pj_debits.empty:
                            # Agrupar por nome do favorecido PJ (padronizado)
                            df_chart_data = df_pj_debits.groupby('nome_favorecido_gestao_financeira')['valor_gestao_financeira'].sum().reset_index()
                            df_chart_data = df_chart_data.sort_values(by='valor_gestao_financeira', ascending=True) # Ascending True para o Plotly ordenar decrescente com o maior no topo
                            
                            st.markdown("<br>", unsafe_allow_html=True)
                            st.markdown("###### 📊 Concentração de Débitos por Pessoa Jurídica (Ordem Decrescente)")
                            
                            fig_pj = px.bar(
                                df_chart_data,
                                x='valor_gestao_financeira',
                                y='nome_favorecido_gestao_financeira',
                                orientation='h',
                                labels={
                                    'valor_gestao_financeira': 'Valor Total Pago (R$)',
                                    'nome_favorecido_gestao_financeira': 'Pessoa Jurídica Beneficiária'
                                },
                                color_discrete_sequence=['#ef4444'] # Cor vermelha elegante para saídas/débitos
                            )
                            
                            fig_pj.update_layout(
                                margin=dict(l=20, r=20, t=10, b=10),
                                height=min(450, max(220, 45 * len(df_chart_data))),
                                paper_bgcolor='rgba(0,0,0,0)',
                                plot_bgcolor='rgba(0,0,0,0)',
                                xaxis=dict(gridcolor='#e2e8f0', title='Valor Total Pago (R$)'),
                                yaxis=dict(title=None, categoryorder='total ascending')
                            )
                            
                            st.plotly_chart(fig_pj, width="stretch")
                            
                    # --- SEÇÃO DE LICITAÇÕES SIMILARES POR OBJETIVOS ---
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.markdown("##### 🔍 Licitações Municipais Associadas (Por Similaridade de Objeto e Empresa Contratada)")
                    
                    df_muni_lic = df_lic[df_lic['municipio_norm'] == muni_norm].copy()
                    
                    if df_muni_lic.empty:
                        st.info("Nenhuma licitação de obra cadastrada no TCE para este município.")
                    else:
                        col_s1, col_s2 = st.columns([4, 6])
                        with col_s1:
                            threshold = st.slider(
                                "Sensibilidade de Comparação (similaridade mínima):",
                                min_value=10, max_value=90, value=25, step=5,
                                format="%d%%",
                                key=f"slider_sim_{muni_norm}_{selected_code}"
                            )
                        
                        def extract_num_year(text):
                            if not isinstance(text, str):
                                return set()
                            matches = re.findall(r'(\d+)[/-](\d{4})', text)
                            res = set()
                            for num, year in matches:
                                res.add((int(num), int(year)))
                            return res

                        # Função para verificar se a empresa contratada da licitação recebeu pagamentos da emenda
                        def check_paid_contractor(lic_row):
                            edital_pairs = extract_num_year(lic_row['Número do Edital'])
                            if not edital_pairs or not pjs_paid_cnpjs:
                                return False, ""
                            
                            for _, emp in muni_tce_df.iterrows():
                                emp_pairs = extract_num_year(emp['nr_licitacao'])
                                if edital_pairs.intersection(emp_pairs):
                                    emp_cnpj = "".join([c for c in str(emp['cnpj_cpf']).split('.')[0] if c.isdigit()])
                                    emp_cnpj_padded = emp_cnpj.zfill(14) if len(emp_cnpj) > 11 else emp_cnpj.zfill(11)
                                    if emp_cnpj_padded in pjs_paid_cnpjs:
                                        # Formatar CNPJ/CPF bonitinho
                                        if len(emp_cnpj_padded) == 14:
                                            cnpj_fmt = f"{emp_cnpj_padded[:2]}.{emp_cnpj_padded[2:5]}.{emp_cnpj_padded[5:8]}/{emp_cnpj_padded[8:12]}-{emp_cnpj_padded[12:]}"
                                        else:
                                            cnpj_fmt = f"{emp_cnpj_padded[:3]}.{emp_cnpj_padded[3:6]}.{emp_cnpj_padded[6:9]}-{emp_cnpj_padded[9:]}"
                                        return True, f"Empresa Beneficiária de Pagamento: {emp['credor']} (CNPJ/CPF: {cnpj_fmt})"
                            return False, ""

                        # Aplicar cálculo de similaridade e verificação de empresa contratada paga
                        sim_data = []
                        for idx, row in df_muni_lic.iterrows():
                            # 1. Calcular similaridade por objeto
                            best_score = 0.0
                            best_src = "Nenhum"
                            
                            # Comparar com objeto da emenda
                            if objeto and objeto != "Objeto não informado no cadastro offline.":
                                score_api = calculate_similarity_jaccard(objeto, row['Objeto Licitação'])
                                if score_api > best_score:
                                    best_score = score_api
                                    best_src = "Objeto Pactuado (API/CSV)"
                                    
                            # Comparar com empenhos
                            linked_empenhos = muni_tce_df[muni_tce_df['codigo_emenda'] == selected_code]
                            if not linked_empenhos.empty:
                                for _, emp in linked_empenhos.iterrows():
                                    score_emp = calculate_similarity_jaccard(emp['historico'], row['Objeto Licitação'])
                                    if score_emp > best_score:
                                        best_score = score_emp
                                        best_src = f"Empenho Nº {emp['num_empenho']}/{emp['ano_empenho']}"
                            
                            # 2. Verificar se a empresa contratada recebeu pagamentos
                            is_paid, paid_src = check_paid_contractor(row)
                            if is_paid:
                                best_score = max(best_score, 1.0)  # Força 100% de similaridade/associação para ficar no topo
                                best_src = paid_src
                                
                            sim_data.append((best_score, best_src, is_paid))
                            
                        # Desempacotar resultados
                        df_muni_lic['Similaridade'] = [s[0] for s in sim_data]
                        df_muni_lic['Origem'] = [s[1] for s in sim_data]
                        df_muni_lic['Forçado'] = [s[2] for s in sim_data]
                        
                        # Filtro por threshold ou forçados por pagamento
                        df_matches = df_muni_lic[(df_muni_lic['Similaridade'] >= (threshold / 100.0)) | df_muni_lic['Forçado']].copy()
                        
                        if df_matches.empty:
                            st.warning(f"Nenhuma licitação encontrada com similaridade de objeto superior a {threshold}%. Experimente reduzir a sensibilidade no slider.")
                        else:
                            df_matches = df_matches.sort_values(by='Similaridade', ascending=False)
                            df_matches_show = df_matches[['Número do Edital', 'Modalidade', 'Objeto Licitação', 
                                                          'Valor previsto licitação', 'Situação do Processo Licitatório', 'Similaridade', 'Origem']].copy()
                            
                            df_matches_show['Similaridade (%)'] = (df_matches_show['Similaridade'] * 100).apply(lambda x: f"{x:.1f}%")
                            df_matches_show['Valor Previsto'] = df_matches_show['Valor previsto licitação'].apply(format_currency)
                            
                            df_matches_show = df_matches_show.drop(columns=['Similaridade', 'Valor previsto licitação'])
                            df_matches_show.columns = ['Edital', 'Modalidade', 'Objeto da Licitação', 'Situação', 'Origem da Similaridade', 'Similaridade (%)', 'Valor Previsto']
                            df_matches_show = df_matches_show[['Edital', 'Modalidade', 'Objeto da Licitação', 'Valor Previsto', 'Situação', 'Similaridade (%)', 'Origem da Similaridade']]
                            
                            st.dataframe(df_matches_show, width="stretch", hide_index=True)
                else:
                    st.info("💡 Selecione uma linha na tabela acima para consultar o objeto pactuado e dados de conta bancária desta emenda na API do Transferegov.")
                    
        # ----------------- ABA 2: EMPENHOS DE OBRAS E MAT. PERMANENTES -----------------
        with tab_obras:
            st.subheader("Empenhos de Obras e Mat. Permanentes")
            if muni_tce_df.empty:
                st.info("Nenhum empenho de obras e material permanente encontrado no TCE-SC para este município.")
            else:
                # Classificar empenhos em vinculados a emendas específicas ou gerais
                df_linked = muni_tce_df[muni_tce_df['codigo_emenda'].notna()].copy()
                df_unlinked = muni_tce_df[muni_tce_df['codigo_emenda'].isna()].copy()
                
                st.markdown(f"**Total de Empenhos de Obras e Material Permanente:** {len(muni_tce_df)} "
                            f"(🔗 {len(df_linked)} vinculados a emendas específicas via texto | ⚖️ {len(df_unlinked)} empenhos gerais)")
                
                # Opção de filtro de exibição
                exibicao_empenhos = st.radio(
                    "Filtrar lista de empenhos:",
                    ["Todos os Empenhos", "Somente Vinculados a Emendas específicas", "Somente Empenhos Gerais (Sem código explícito)"],
                    horizontal=True
                )
                
                if exibicao_empenhos == "Somente Vinculados a Emendas específicas":
                    df_obras_filtered = df_linked
                elif exibicao_empenhos == "Somente Empenhos Gerais (Sem código explícito)":
                    df_obras_filtered = df_unlinked
                else:
                    df_obras_filtered = muni_tce_df
                    
                if df_obras_filtered.empty:
                    st.warning("Nenhum empenho para o filtro selecionado.")
                else:
                    # Mostrar tabela customizada de empenhos
                    df_tce_show = df_obras_filtered[['num_empenho', 'ano_empenho', 'data_empenho', 'credor', 
                                                     'valor_empenhado', 'valor_pago', 'codigo_emenda', 'nr_licitacao', 'historico']].copy()
                    
                    # Funções de extração local para licitação e contrato
                    def split_lic(val):
                        parts = [p.strip() for p in re.split(r'\s+/\s+', str(val))]
                        return parts[0] if len(parts) > 0 else "Sem Info"
                        
                    def split_cont(val):
                        parts = [p.strip() for p in re.split(r'\s+/\s+', str(val))]
                        return parts[1] if len(parts) > 1 else "Sem Info"
                        
                    df_tce_show['Licitação'] = df_tce_show['nr_licitacao'].apply(split_lic)
                    df_tce_show['Contrato'] = df_tce_show['nr_licitacao'].apply(split_cont)
                    
                    df_tce_show['Vínculo Emenda'] = df_tce_show['codigo_emenda'].apply(
                        lambda x: f"🔗 {int(x)}" if pd.notna(x) else "Geral (Sem cód. explícito)"
                    )
                    
                    df_tce_show = df_tce_show.drop(columns=['codigo_emenda', 'nr_licitacao'])
                    df_tce_show.columns = ['Nº Empenho', 'Ano', 'Data', 'Empresa Contratada', 
                                           'Vl. Empenhado (R$)', 'Vl. Pago (R$)', 'Descrição do Objeto', 'Licitação', 'Contrato', 'Origem/Vínculo']
                    
                    # Reordenar colunas
                    df_tce_show = df_tce_show[['Nº Empenho', 'Ano', 'Data', 'Empresa Contratada', 
                                               'Licitação', 'Contrato', 'Descrição do Objeto', 'Vl. Empenhado (R$)', 'Vl. Pago (R$)', 'Origem/Vínculo']]
                    
                    df_tce_show['Vl. Empenhado (R$)'] = df_tce_show['Vl. Empenhado (R$)'].apply(format_currency)
                    df_tce_show['Vl. Pago (R$)'] = df_tce_show['Vl. Pago (R$)'].apply(format_currency)
                    
                    st.dataframe(df_tce_show, width="stretch", hide_index=True)
                    
        # ----------------- ABA 3: EMPRESAS CONTRATADAS -----------------
        with tab_empresas:
            st.subheader("Lista de Empresas Habilitadas e Contratadas")
            if muni_tce_df.empty:
                st.info("Nenhuma empresa contratada encontrada na base do TCE para este município.")
            else:
                # Agrupar dados por CNPJ/CPF da empresa
                df_credores = muni_tce_df.groupby(['cnpj_cpf', 'credor']).agg(
                    total_empenhado=('valor_empenhado', 'sum'),
                    total_pago=('valor_pago', 'sum'),
                    num_empenhos=('num_empenho', 'count')
                ).reset_index().sort_values(by='total_empenhado', ascending=False)
                
                df_credores_show = df_credores.copy()
                df_credores_show.columns = ['CNPJ/CPF', 'Nome do Credor/Empresa', 'Total Empenhado (R$)', 'Total Pago (R$)', 'Qtd. Empenhos']
                
                df_credores_show['Total Empenhado (R$)'] = df_credores_show['Total Empenhado (R$)'].apply(format_currency)
                df_credores_show['Total Pago (R$)'] = df_credores_show['Total Pago (R$)'].apply(format_currency)
                
                col_tab3_1, col_tab3_2 = st.columns([6, 4])
                
                with col_tab3_1:
                    st.dataframe(df_credores_show, width="stretch", hide_index=True)
                
                with col_tab3_2:
                    # Bar chart dos maiores credores
                    df_top_cred = df_credores.head(5)
                    fig_cred = px.bar(
                        df_top_cred,
                        x='total_empenhado',
                        y='credor',
                        orientation='h',
                        title='Top 5 Empresas por Valor Empenhado (R$)',
                        labels={'total_empenhado': 'Total Empenhado (R$)', 'credor': 'Empresa'},
                        color='total_empenhado',
                        color_continuous_scale=px.colors.sequential.Turbo
                    )
                    fig_cred.update_layout(yaxis={'categoryorder':'total ascending'}, showlegend=False, coloraxis_showscale=False)
                    st.plotly_chart(fig_cred, width="stretch")
                    
        # ----------------- ABA 4: HISTÓRICO TEXTUAL E LINKS -----------------
        with tab_historico:
            st.subheader("Histórico Detalhado dos Empenhos (Obras e Materiais Permanentes)")
            if muni_tce_df.empty:
                st.info("Histórico de empenhos indisponível para este município.")
            else:
                # Adicionar busca por palavra-chave no histórico
                busca_termo = st.text_input("Filtrar histórico por palavra-chave (ex: asfalto, creche, ginásio):", "")
                
                df_hist_filtered = muni_tce_df.copy()
                if busca_termo:
                    df_hist_filtered = df_hist_filtered[
                        df_hist_filtered['historico'].str.contains(busca_termo, case=False, na=False) |
                        df_hist_filtered['credor'].str.contains(busca_termo, case=False, na=False)
                    ]
                
                st.markdown(f"**Registros encontrados:** {len(df_hist_filtered)}")
                st.markdown("---")
                
                # Exibir cada registro em formato de cartão
                for idx, row in df_hist_filtered.iterrows():
                    # Extrair URLs do histórico
                    text = row['historico']
                    extracted_urls = re.findall(r'https?://[^\s,;()]+', text)
                    
                    # Gerar link do Google como ferramenta de busca adicional
                    query = f"empenho {row['num_empenho']} {row['ano_empenho']} {muni_name} Santa Catarina obras e materiais permanentes"
                    google_search_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
                    
                    # Estilo visual do cartão do histórico
                    st.markdown(f"""
                    <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 18px; margin-bottom: 16px; box-shadow: 0 2px 4px rgba(0,0,0,0.01);">
                        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #cbd5e1; padding-bottom: 8px; margin-bottom: 10px;">
                            <span style="font-weight: 700; color: #1e3a8a;">Empenho Nº {row['num_empenho']} / {row['ano_empenho']} ({row['data_empenho']})</span>
                            <span style="font-weight: 600; color: #475569; font-size: 0.9rem;">
                                Empenhado: <span style="color:#b45309;">{format_currency(row['valor_empenhado'])}</span> | Pago: <span style="color:#047857;">{format_currency(row['valor_pago'])}</span>
                            </span>
                        </div>
                        <div style="margin-bottom: 10px;">
                            <strong>Empresa:</strong> {row['credor']} (CNPJ/CPF: {row['cnpj_cpf']})
                        </div>
                        <div style="margin-bottom: 12px; font-style: italic; color: #334155; line-height: 1.5; font-size: 0.95rem; background: #ffffff; padding: 10px; border-radius: 6px; border: 1px solid #f1f5f9;">
                            "{row['historico']}"
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Renderizar botões de links
                    col_b1, col_b2 = st.columns([1, 4])
                    with col_b1:
                        st.markdown(f'<a href="{google_search_url}" target="_blank"><button style="cursor:pointer; background-color:#2563eb; color:white; border:none; padding:6px 12px; border-radius:6px; font-weight:600; font-size:0.85rem;">🔍 Buscar no Google</button></a>', unsafe_allow_html=True)
                    
                    if extracted_urls:
                        with col_b2:
                            for url in extracted_urls:
                                st.markdown(f'<a href="{url}" target="_blank"><button style="cursor:pointer; background-color:#10b981; color:white; border:none; padding:6px 12px; border-radius:6px; font-weight:600; font-size:0.85rem; margin-right:8px;">🔗 Acessar Link Externo ({url.split("//")[-1][:20]}...)</button></a>', unsafe_allow_html=True)
                    
                    st.markdown("<div style='margin-bottom: 25px;'></div>", unsafe_allow_html=True)
