import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import json # Adicionamos a biblioteca para ler o ficheiro JSON

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Coach de Concursos",
    page_icon="🎯",
    layout="centered",
    initial_sidebar_state="expanded"
)

# --- INICIALIZAÇÃO INTELIGENTE DO FIREBASE (COM CACHE) ---
# Usamos @st.cache_resource para garantir que a conexão seja feita apenas uma vez por sessão.
@st.cache_resource
def inicializar_firebase():
    """
    Inicializa a conexão com o Firebase de forma inteligente.
    Tenta usar os Secrets do Streamlit primeiro (para a nuvem).
    Se apanhar um erro de ficheiro não encontrado, tenta usar o ficheiro local (para desenvolvimento).
    """
    creds_dict = None
    try:
        # Método 1: Tentar carregar as credenciais a partir dos Secrets do Streamlit (para a nuvem)
        creds_dict = st.secrets["firebase_credentials"]
        st.session_state.firebase_initialized_from = "secrets"
    except FileNotFoundError:
        # Se o ficheiro de secrets não for encontrado (ambiente local), tenta o método 2
        st.info("Ficheiro de secrets não encontrado. A tentar carregar credenciais locais...")
        try:
            with open("firebase_credentials.json") as f:
                creds_dict = json.load(f)
            st.session_state.firebase_initialized_from = "local_file"
        except FileNotFoundError:
            st.error("ERRO CRÍTICO: Ficheiro 'firebase_credentials.json' não encontrado na pasta do projeto.")
            return None
            
    except Exception as e: # Apanha outros erros relacionados aos secrets
        st.error(f"Ocorreu um erro ao ler os secrets: {e}")
        return None

    # Se as credenciais foram carregadas com sucesso (de qualquer método)
    if creds_dict:
        try:
            cred = credentials.Certificate(creds_dict)
            if not firebase_admin._apps:
                firebase_admin.initialize_app(cred)
            return firestore.client()
        except Exception as e:
            st.error(f"Erro ao inicializar o Firebase com as credenciais fornecidas: {e}")
            return None
    
    # Se nenhuma credencial foi encontrada
    st.error("Não foi possível encontrar as credenciais do Firebase (nem nos secrets, nem em ficheiro local).")
    return None


# --- EXECUTA A INICIALIZAÇÃO ---
db = inicializar_firebase()

# Se a inicialização falhar, para a execução.
if db is None:
    st.stop()

# --- LÓGICA DA PÁGINA PRINCIPAL ---
st.title("🎯 Coach de Concursos Online")
st.write("A sua plataforma personalizada para gestão de estudos.")

st.subheader("Selecione um Perfil de Estudo Ativo")

# Carrega os perfis ativos
try:
    perfis_ref = db.collection('perfis_concursos').where(field_path='status', op_string='==', value='Ativo').stream()
    perfis_ativos_docs = list(perfis_ref)
    
    perfis_ativos = []
    for doc in perfis_ativos_docs:
        perfil = doc.to_dict()
        perfil['id_documento'] = doc.id
        perfis_ativos.append(perfil)
    
    # Adiciona uma opção vazia para o seletor
    opcoes_perfis = ["-"] + [f"{p['nome']} ({p['ano']})" for p in perfis_ativos]
    
    perfil_display_selecionado = st.selectbox(
        "Escolha o concurso que deseja estudar hoje:",
        options=opcoes_perfis,
        index=0 # Começa com a opção "-" selecionada
    )

    if perfil_display_selecionado != "-":
        # Encontra o dicionário completo do perfil selecionado
        perfil_selecionado_completo = next((p for p in perfis_ativos if f"{p['nome']} ({p['ano']})" == perfil_display_selecionado), None)
        
        # Guarda o perfil na memória da sessão para que as outras páginas o possam usar
        st.session_state.perfil_selecionado = perfil_selecionado_completo
        st.success(f"Perfil **{perfil_selecionado_completo['nome']}** carregado com sucesso!")
        st.info("Pode agora navegar para as outras páginas no menu à esquerda.")

except Exception as e:
    st.error(f"Não foi possível carregar os perfis de estudo. Erro: {e}")

st.sidebar.info("Desenvolvido por Grégori e Gemini.")

