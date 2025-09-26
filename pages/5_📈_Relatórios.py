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

@st.cache_data(ttl=300)
def carregar_dashboard_df(_perfil):
    """Carrega a tabela de performance de um perfil."""
    if not _perfil or not db:
        return pd.DataFrame()
    try:
        colecao_dashboard = _perfil.get('colecao_dashboard')
        docs = db.collection(colecao_dashboard).stream()
        df = pd.DataFrame([doc.to_dict() for doc in docs])

        df.rename(columns={
            'Total_Questoes_Topico': 'Qsts',
            'Total_Acertos_Topico': 'Acertos',
            'Ultima_Medicao': 'Últ. Medição'
        }, inplace=True, errors='ignore')

        for col in ['Qsts', 'Acertos', '%']:
            if col not in df.columns:
                df[col] = 0
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar o dashboard: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_historico_df(_perfil):
    """Carrega o histórico de estudos de um perfil."""
    if not _perfil or not db:
        return pd.DataFrame()
    try:
        colecao_historico = _perfil.get('colecao_historico')
        docs = db.collection(colecao_historico).stream()
        df = pd.DataFrame([doc.to_dict() for doc in docs])
        return df
    except Exception as e:
        st.error(f"Erro ao carregar o histórico de estudos: {e}")
        return pd.DataFrame()


# --- LÓGICA DA PÁGINA ---
st.set_page_config(page_title="Relatórios Analíticos", page_icon="📈", layout="wide")

st.markdown("# 📈 Relatórios Analíticos")
st.markdown("Analise o seu progresso com visões consolidadas do seu desempenho.")

if 'perfil_selecionado' in st.session_state and st.session_state.perfil_selecionado:
    perfil = st.session_state.perfil_selecionado
    st.info(f"A exibir relatórios para o concurso: **{perfil['nome']}**")

    df_dashboard = carregar_dashboard_df(perfil)
    df_historico = carregar_historico_df(perfil)

    tab1, tab2 = st.tabs(["Performance por Disciplina", "Atividade Diária"])

    with tab1:
        st.subheader("📊 Relatório de Performance por Disciplina")
        if not df_dashboard.empty:
            # Lógica do relatório por disciplina (existente)
            relatorio_disciplina = df_dashboard.groupby('Disciplina').agg(
                total_questoes=('Qsts', 'sum'),
                total_acertos=('Acertos', 'sum'),
                media_performance=('%', 'mean')
            ).reset_index()
            relatorio_disciplina['performance_geral'] = ((relatorio_disciplina['total_acertos'] / relatorio_disciplina['total_questoes']) * 100).fillna(0)
            total_topicos = df_dashboard.groupby('Disciplina')['ID'].count().reset_index().rename(columns={'ID': 'total_topicos'})
            topicos_medidos = df_dashboard[df_dashboard['Domínio'] != '[Não Medido]'].groupby('Disciplina')['ID'].count().reset_index().rename(columns={'ID': 'topicos_medidos'})
            relatorio_disciplina = pd.merge(relatorio_disciplina, total_topicos, on='Disciplina', how='left')
            relatorio_disciplina = pd.merge(relatorio_disciplina, topicos_medidos, on='Disciplina', how='left').fillna(0)
            relatorio_disciplina['progresso_medicao'] = ((relatorio_disciplina['topicos_medidos'] / relatorio_disciplina['total_topicos']) * 100).fillna(0)
            
            relatorio_final_df = relatorio_disciplina[['Disciplina', 'total_questoes', 'total_acertos', 'performance_geral', 'media_performance', 'topicos_medidos', 'total_topicos', 'progresso_medicao']]
            relatorio_final_df.columns = ['Disciplina', 'Total Questões', 'Total Acertos', 'Performance Geral (%)', 'Média de Performance (%)', 'Tópicos Medidos', 'Total Tópicos', 'Progresso da Medição (%)']
            
            st.dataframe(relatorio_final_df, column_config={
                "Performance Geral (%)": st.column_config.ProgressColumn(format="%.2f%%", min_value=0, max_value=100),
                "Média de Performance (%)": st.column_config.ProgressColumn(format="%.2f%%", min_value=0, max_value=100),
                "Progresso da Medição (%)": st.column_config.ProgressColumn(format="%.2f%%", min_value=0, max_value=100)},
                hide_index=True, use_container_width=True
            )
        else:
            st.warning("Não há dados no dashboard para gerar este relatório.")

    with tab2:
        st.subheader("📅 Relatório de Atividade Diária")
        if not df_historico.empty and 'Data' in df_historico.columns:
            # Garante que a coluna 'Data' está no formato correto
            df_historico['Data'] = pd.to_datetime(df_historico['Data'], format='%d/%m/%Y', errors='coerce')
            df_historico.dropna(subset=['Data'], inplace=True) # Remove linhas onde a data não pôde ser convertida

            # Agrupa por data e calcula os totais
            relatorio_diario = df_historico.groupby(df_historico['Data'].dt.date).agg(
                Total_Questoes=('Total_Questoes', 'sum'),
                Acertos=('Acertos', 'sum')
            ).reset_index()

            relatorio_diario['% Acerto'] = ((relatorio_diario['Acertos'] / relatorio_diario['Total_Questoes']) * 100).fillna(0)
            
            # Ordena do mais recente para o mais antigo
            relatorio_diario = relatorio_diario.sort_values(by='Data', ascending=False)
            
            # Formata a data para exibição
            relatorio_diario['Data'] = pd.to_datetime(relatorio_diario['Data']).dt.strftime('%d/%m/%Y')

            st.markdown("##### Volume de Questões por Dia")
            
            # Prepara dados para o gráfico
            chart_data = relatorio_diario.rename(columns={'Data': 'index'}).set_index('index')
            st.bar_chart(chart_data['Total_Questoes'])
            
            st.markdown("##### Detalhe da Atividade Diária")
            st.dataframe(relatorio_diario, hide_index=True, use_container_width=True,
                column_config={
                    "% Acerto": st.column_config.ProgressColumn(format="%.2f%%", min_value=0, max_value=100)
                }
            )
        else:
            st.warning("Ainda não há lançamentos no seu histórico para gerar este relatório.")

else:
    st.warning("Por favor, selecione um perfil na página principal para começar.")
    st.page_link("app_gui.py", label="Ir para a Página Principal", icon="🏠")

