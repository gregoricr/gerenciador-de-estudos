import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import os

# --- INICIALIZAÇÃO INTELIGENTE E ROBUSTA DO FIREBASE (VERSÃO FINAL) ---
@st.cache_resource
def inicializar_firebase():
    """
    Inicializa a conexão com o Firebase de forma inteligente e à prova de falhas.
    Prioriza a verificação do ficheiro local e depois tenta os secrets da nuvem com diagnóstico preciso.
    """
    try:
        # MÉTODO 1: LOCAL (Prioridade para desenvolvimento)
        if os.path.exists('firebase_credentials.json'):
            if not firebase_admin._apps:
                cred = credentials.Certificate('firebase_credentials.json')
                firebase_admin.initialize_app(cred)
            return firestore.client()

        # MÉTODO 2: NUVEM (Streamlit Secrets com Verificação Completa e Individual)
        required_secrets = [
            "type", "project_id", "private_key_id", "private_key",
            "client_email", "client_id", "auth_uri", "token_uri",
            "auth_provider_x509_cert_url", "client_x509_cert_url", "universe_domain"
        ]
        
        # Verifica se todas as chaves necessárias existem nos secrets
        if all(secret in st.secrets for secret in required_secrets):
            cred_dict = {key: st.secrets.get(key) for key in required_secrets}
            # Corrige a formatação da chave privada que é corrompida pelo Streamlit
            cred_dict["private_key"] = cred_dict["private_key"].replace('\\n', '\n')
            
            if not firebase_admin._apps:
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
            return firestore.client()
        else:
            # Diagnóstico preciso: informa quais chaves estão em falta
            missing_secrets = [secret for secret in required_secrets if secret not in st.secrets]
            if not missing_secrets:
                raise ValueError("A configuração de Secrets parece estar vazia.")
            else:
                raise ValueError(f"Configuração de Secrets incompleta. As seguintes chaves estão em falta: {missing_secrets}")

    except Exception as e:
        st.error(f"Erro crítico ao inicializar o Firebase: {e}")
        st.error("Verifique a sua configuração de Secrets no painel do Streamlit Cloud ou o seu ficheiro 'firebase_credentials.json' local.")
        return None

# --- O RESTO DO CÓDIGO PERMANECE O MESMO ---

# --- LÓGICA DA PÁGINA PRINCIPAL ---
st.set_page_config(
    page_title="Coach de Concursos",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

db = inicializar_firebase()

st.title("🎯 Coach de Concursos")
st.markdown("A sua plataforma personalizada para gestão de estudos.")

if db:
    # --- Carregar e selecionar perfis ---
    try:
        perfis_ref = db.collection('perfis_concursos').where('status', '==', 'Ativo').stream()
        perfis_ativos = {doc.id: doc.to_dict() for doc in perfis_ref}
    except Exception as e:
        st.error(f"Não foi possível carregar os perfis da base de dados: {e}")
        perfis_ativos = {}

    if not perfis_ativos:
        st.info("Nenhum perfil de estudo ativo encontrado.")
        st.warning("Vá a 'Gerenciar Perfis' para criar um novo perfil ou reativar um existente.")
    else:
        st.header("Selecione um Perfil de Estudo Ativo")

        # Cria uma lista de opções para o selectbox
        opcoes_perfis = {perfil_id: f"{data['nome']} ({data['ano']})" for perfil_id, data in perfis_ativos.items()}
        
        # Tenta manter o perfil selecionado anteriormente
        indice_selecionado = 0
        if 'perfil_id_selecionado' in st.session_state:
            ids_opcoes = list(opcoes_perfis.keys())
            if st.session_state.perfil_id_selecionado in ids_opcoes:
                indice_selecionado = ids_opcoes.index(st.session_state.perfil_id_selecionado)

        perfil_id_selecionado = st.selectbox(
            "Escolha o concurso que deseja estudar hoje:",
            options=opcoes_perfis.keys(),
            format_func=lambda x: opcoes_perfis[x],
            index=indice_selecionado,
            placeholder="Selecione um perfil..."
        )

        if st.button("Carregar Perfil Selecionado", type="primary"):
            if perfil_id_selecionado:
                st.session_state.perfil_selecionado = perfis_ativos[perfil_id_selecionado]
                st.session_state.perfil_id_selecionado = perfil_id_selecionado
                st.success(f"Perfil '{perfis_ativos[perfil_id_selecionado]['nome']}' carregado com sucesso!")
                st.info("Pode agora navegar para as outras páginas no menu à esquerda.")
            else:
                st.warning("Por favor, selecione um perfil.")

    st.markdown("---")
    if 'perfil_selecionado' in st.session_state and st.session_state.perfil_selecionado:
        perfil_atual = st.session_state.perfil_selecionado
        st.sidebar.success(f"Perfil Ativo:\n**{perfil_atual['nome']}**")
    else:
        st.sidebar.warning("Nenhum perfil carregado.")
else:
    st.error("A aplicação não conseguiu conectar-se à base de dados. As funcionalidades estão desativadas.")