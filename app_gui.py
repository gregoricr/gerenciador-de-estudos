# Importando as bibliotecas necessárias
import streamlit as st
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
import json
import os

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Coach de Concursos",
    page_icon="📊",
    layout="wide"
)

# --- FUNÇÃO DE INICIALIZAÇÃO DO FIREBASE (ADAPTADA PARA A NUVEM) ---
@st.cache_resource
def inicializar_firebase():
    """
    Inicializa a conexão com o Firebase de forma segura, usando Streamlit Secrets
    quando a aplicação estiver online (deployed).
    """
    try:
        # Verifica se já existe uma instância do Firebase rodando
        if not firebase_admin._apps:
            # Tenta carregar as credenciais a partir dos Secrets do Streamlit
            if 'firebase_credentials' in st.secrets:
                creds_json = st.secrets["firebase_credentials"]
                creds_dict = json.loads(creds_json) if isinstance(creds_json, str) else creds_json
                cred = credentials.Certificate(creds_dict)
                st.session_state.firebase_init_method = "Secrets"
            # Se não estiver na nuvem, procura pelo arquivo local
            elif os.path.exists("firebase_credentials.json"):
                cred = credentials.Certificate("firebase_credentials.json")
                st.session_state.firebase_init_method = "Local File"
            else:
                st.error("Credenciais do Firebase não encontradas. Verifique o arquivo 'firebase_credentials.json' ou os Secrets do Streamlit.")
                return None
            
            firebase_admin.initialize_app(cred)
        
        return firestore.client()

    except Exception as e:
        st.error(f"Erro ao inicializar o Firebase: {e}")
        return None

# Inicializa o Firebase e guarda o cliente na sessão
if 'db' not in st.session_state:
    st.session_state.db = inicializar_firebase()

db = st.session_state.db

# --- FUNÇÕES DE DADOS ---
@st.cache_data(ttl=300) # Cache de 5 minutos
def carregar_dashboard():
    """Carrega os dados do Firebase e retorna um DataFrame."""
    if not db:
        return pd.DataFrame()
        
    try:
        docs = db.collection('dashboard').stream()
        lista_de_topicos = [doc.to_dict() for doc in docs]
        
        if not lista_de_topicos:
            return pd.DataFrame()

        df_bruto = pd.DataFrame(lista_de_topicos)
        
        # Define a estrutura final e limpa da tabela
        colunas_finais = ['ID', 'Disciplina', 'Tópico do Edital', 'Teoria (T)', 'Domínio', '%', 'Últ. Medição']
        df_final = pd.DataFrame(columns=colunas_finais)

        # Copia os dados para a tabela final de forma segura
        for col in colunas_finais:
            if col == 'Últ. Medição':
                df_final[col] = df_bruto.get('Ultima_Medicao')
            else:
                df_final[col] = df_bruto.get(col)

        df_final.fillna('-', inplace=True)
        df_final['ID'] = pd.to_numeric(df_final['ID'])
        df_final = df_final.sort_values(by='ID').reset_index(drop=True)
        
        return df_final[colunas_finais]

    except Exception as e:
        st.error(f"Erro ao carregar dados do Firebase: {e}")
        return pd.DataFrame()

# --- INTERFACE GRÁFICA ---
st.title("📊 Dashboard de Performance Completo")
st.markdown("---")

if st.button("Recarregar Dados da Nuvem"):
    st.cache_data.clear() # Limpa o cache para forçar a releitura

# Carrega e exibe o dashboard
if db:
    dashboard_df = carregar_dashboard()
    if not dashboard_df.empty:
        st.dataframe(dashboard_df, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum dado encontrado no dashboard. Comece a registrar seus estudos!")
else:
    st.warning("A conexão com o banco de dados não pôde ser estabelecida.")