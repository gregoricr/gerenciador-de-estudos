import streamlit as st
import pandas as pd
from firebase_admin import firestore

# --- FUNÇÕES AUXILIARES ---

@st.cache_resource
def get_db_connection():
    """Obtém a conexão com o cliente do Firestore."""
    try:
        return firestore.client()
    except Exception:
        return None

db = get_db_connection()

# --- FUNÇÃO DE CARREGAMENTO CORRIGIDA (VERSÃO FINAL E ROBUSTA) ---
@st.cache_data(ttl=300)
def carregar_dashboard_df(_perfil):
    """Carrega a tabela de performance de um perfil, garantindo que todas as colunas sejam exibidas."""
    if not _perfil or not db:
        return pd.DataFrame()
    try:
        colecao_dashboard = _perfil.get('colecao_dashboard')
        docs = db.collection(colecao_dashboard).stream()
        lista_de_topicos = [doc.to_dict() for doc in docs]

        if not lista_de_topicos:
            return pd.DataFrame()

        df = pd.DataFrame(lista_de_topicos)

        # 1. Renomeia colunas antigas para o padrão de exibição, se existirem
        df.rename(columns={
            'Total_Questoes_Topico': 'Qsts', 
            'Total_Acertos_Topico': 'Acertos', 
            'Ultima_Medicao': 'Últ. Medição'
        }, inplace=True, errors='ignore')

        # 2. Define o "molde" com todas as colunas finais e na ordem correta
        colunas_finais = ['ID', 'Disciplina', 'Tópico do Edital', 'Teoria (T)', 'Qsts', 'Acertos', 'Domínio', '%', 'Últ. Medição']
        
        # 3. Reindexa o DataFrame. Isto força o DataFrame a ter exatamente estas colunas.
        # As que já existem são mantidas, as que faltam são adicionadas com o valor NaN (vazio).
        df = df.reindex(columns=colunas_finais)

        # 4. Preenche todos os valores vazios (NaN) com os padrões corretos
        valores_padrao = {
            'Qsts': 0, 
            'Acertos': 0, 
            '%': 0,
            'ID': 0,
            'Disciplina': 'N/A', 
            'Tópico do Edital': '-', 
            'Teoria (T)': '[ ]',
            'Domínio': '[Não Medido]',
            'Últ. Medição': '-'
        }
        df.fillna(value=valores_padrao, inplace=True)

        # 5. Converte os tipos de dados para garantir a formatação correta
        df['ID'] = pd.to_numeric(df['ID']).astype(int)
        df['Qsts'] = pd.to_numeric(df['Qsts']).astype(int)
        df['Acertos'] = pd.to_numeric(df['Acertos']).astype(int)
        df['%'] = pd.to_numeric(df['%'])

        # 6. Ordena pelo ID para garantir a ordem do edital
        df = df.sort_values(by='ID').reset_index(drop=True)
        
        return df
        
    except Exception as e:
        st.error(f"Erro ao carregar o dashboard: {e}")
        return pd.DataFrame()


# --- LÓGICA DA PÁGINA ---
st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")

st.markdown("# 📊 Dashboard de Performance")

if 'perfil_selecionado' in st.session_state and st.session_state.perfil_selecionado:
    perfil = st.session_state.perfil_selecionado
    st.info(f"Exibindo dados para o concurso: **{perfil['nome']}**")

    if st.button("Recarregar Dados da Nuvem", type="primary"):
        st.cache_data.clear()
        st.rerun()

    df_dashboard = carregar_dashboard_df(perfil)

    if not df_dashboard.empty:
        st.dataframe(df_dashboard, use_container_width=True, hide_index=True)
    else:
        st.warning("Ainda não há dados no dashboard para este perfil.")
else:
    st.warning("Por favor, selecione um perfil na página principal para começar.")
    st.page_link("app_gui.py", label="Ir para a Página Principal", icon="🏠")

