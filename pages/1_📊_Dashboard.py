import streamlit as st
import pandas as pd
from firebase_admin import firestore

# --- FUNÇÕES AUXILIARES ---

# Função para garantir a inicialização do Firebase
@st.cache_resource
def get_db_connection():
    """Obtém a conexão com o cliente do Firestore."""
    try:
        return firestore.client()
    except Exception as e:
        st.error(f"Erro ao obter conexão com o Firebase: {e}")
        return None

db = get_db_connection()

# Função para carregar os dados do dashboard de um perfil
@st.cache_data(ttl=60)
def carregar_dashboard_df(_perfil):
    """Carrega os dados do Firebase para um perfil específico e retorna um DataFrame."""
    if not _perfil or not db:
        return pd.DataFrame()
        
    colecao_dashboard = _perfil.get('colecao_dashboard')
    if not colecao_dashboard:
        st.error("Informação da coleção do dashboard não encontrada no perfil.")
        return pd.DataFrame()

    try:
        docs = db.collection(colecao_dashboard).stream()
        lista_de_topicos = [doc.to_dict() for doc in docs]
        
        if not lista_de_topicos:
            return pd.DataFrame()

        df_bruto = pd.DataFrame(lista_de_topicos)
        colunas_finais = ['ID', 'Disciplina', 'Tópico do Edital', 'Teoria (T)', 'Qsts', 'Acertos', 'Domínio', '%', 'Últ. Medição']
        df_final = pd.DataFrame()

        # Renomeia colunas legadas e garante a ordem
        df_bruto.rename(columns={'Total_Questoes_Topico': 'Qsts', 
                                 'Total_Acertos_Topico': 'Acertos', 
                                 'Ultima_Medicao': 'Últ. Medição'}, inplace=True, errors='ignore')

        for col in colunas_finais:
            if col in df_bruto.columns:
                df_final[col] = df_bruto[col]
            else:
                df_final[col] = 0 if col in ['Qsts', 'Acertos', '%'] else '-'
        
        df_final.fillna({'Qsts': 0, 'Acertos': 0, '%': 0}, inplace=True)
        df_final.fillna('-', inplace=True)
        
        for col in ['ID', '%', 'Qsts', 'Acertos']:
             df_final[col] = pd.to_numeric(df_final[col], errors='coerce').fillna(0)

        df_final['ID'] = df_final['ID'].astype(int)
        df_final = df_final.sort_values(by='ID').reset_index(drop=True)
        return df_final[colunas_finais]

    except Exception as e:
        st.error(f"Erro ao carregar dados do Firebase: {e}")
        return pd.DataFrame()

# --- LÓGICA DA PÁGINA ---
st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")

st.markdown("# 📊 Dashboard de Performance")

if 'perfil_selecionado' in st.session_state and st.session_state.perfil_selecionado:
    perfil = st.session_state.perfil_selecionado
    st.info(f"Exibindo dados para o concurso: **{perfil['nome']}**")

    if st.button("Recarregar Dados da Nuvem"):
        # Limpa o cache da função específica para forçar a releitura dos dados
        carregar_dashboard_df.clear()
        st.success("Dados recarregados!")

    df_dashboard = carregar_dashboard_df(perfil)

    if not df_dashboard.empty:
        # CORREÇÃO AQUI: Adicionado hide_index=True para ocultar a coluna de índice
        st.dataframe(df_dashboard, hide_index=True, use_container_width=True)

        # Resumo Geral
        total_geral_questoes = df_dashboard['Qsts'].sum()
        total_geral_acertos = df_dashboard['Acertos'].sum()
        
        if total_geral_questoes > 0:
            percentual_geral = (total_geral_acertos / total_geral_questoes) * 100
            st.markdown("---")
            st.subheader("Resumo Geral de Performance")
            col1, col2, col3 = st.columns(3)
            col1.metric("Total de Questões Feitas", f"{int(total_geral_questoes)}")
            col2.metric("Total de Acertos", f"{int(total_geral_acertos)}")
            col3.metric("Percentual de Acerto Geral", f"{percentual_geral:.2f}%")
        
    else:
        st.warning("Ainda não há dados de dashboard para este perfil.")
else:
    st.warning("Por favor, selecione um perfil na página principal para começar.")
    st.page_link("app_principal.py", label="Ir para a Página Principal", icon="🏠")

