import streamlit as st
import pandas as pd
from firebase_admin import firestore
from datetime import datetime

# --- FUNÇÕES AUXILIARES ---

@st.cache_resource
def get_db_connection():
    """Obtém a conexão com o cliente do Firestore."""
    try:
        return firestore.client()
    except Exception:
        return None

db = get_db_connection()

# Funções de carregamento de dados (agora mais específicas)
@st.cache_data(ttl=300)
def carregar_dashboard_df(_perfil):
    if not _perfil or not db:
        return pd.DataFrame()
    try:
        colecao_dashboard = _perfil.get('colecao_dashboard')
        docs = db.collection(colecao_dashboard).stream()
        df = pd.DataFrame([doc.to_dict() for doc in docs])
        return df if not df.empty else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_historico_tempo_df(_perfil):
    if not _perfil or not db:
        return pd.DataFrame()
    try:
        id_perfil = _perfil.get('id_documento')
        if not id_perfil:
            return pd.DataFrame()
        colecao_historico_tempo = f"historico_tempo_{id_perfil}"
        docs = db.collection(colecao_historico_tempo).stream()
        df = pd.DataFrame([doc.to_dict() for doc in docs])
        return df if not df.empty else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

# --- NOVA FUNÇÃO PARA FORMATAR O TEMPO ---
def formatar_minutos(total_minutos):
    """Converte um total de minutos para o formato 'Xh Ymin'."""
    if total_minutos is None or total_minutos < 0:
        return "N/A"
    horas = int(total_minutos // 60)
    minutos = int(total_minutos % 60)
    return f"{horas}h {minutos:02d}min"

# --- LÓGICA DA PÁGINA ---
st.set_page_config(page_title="Relatórios", page_icon="📈", layout="wide")

st.markdown("# 📈 Relatórios Analíticos")
st.markdown("Analise o seu progresso com visões consolidadas do seu desempenho.")

if 'perfil_selecionado' in st.session_state and st.session_state.perfil_selecionado:
    perfil = st.session_state.perfil_selecionado
    st.info(f"A exibir relatórios para o concurso: **{perfil['nome']}**")

    df_dashboard = carregar_dashboard_df(perfil)

    if df_dashboard.empty:
        st.warning("Não há dados de dashboard para este perfil. Lance um simulado para começar a ver os relatórios.")
    else:
        tab1, tab2, tab3 = st.tabs(["Performance por Disciplina", "Atividade Diária", "Tempo de Estudo por Matéria"])

        # --- Aba 1: Performance por Disciplina ---
        with tab1:
            st.subheader("Relatório de Performance por Disciplina")
            df_dashboard.rename(columns={'Total_Questoes_Topico': 'Qsts', 'Total_Acertos_Topico': 'Acertos'}, inplace=True, errors='ignore')
            
            # Garante que as colunas numéricas existam
            if 'Qsts' not in df_dashboard.columns: df_dashboard['Qsts'] = 0
            if 'Acertos' not in df_dashboard.columns: df_dashboard['Acertos'] = 0
            if '%' not in df_dashboard.columns: df_dashboard['%'] = 0
            
            # Converte colunas para numérico, tratando erros
            df_dashboard['Qsts'] = pd.to_numeric(df_dashboard['Qsts'], errors='coerce').fillna(0)
            df_dashboard['Acertos'] = pd.to_numeric(df_dashboard['Acertos'], errors='coerce').fillna(0)
            df_dashboard['%'] = pd.to_numeric(df_dashboard['%'], errors='coerce').fillna(0)


            # Agrupa por disciplina
            relatorio_disciplina = df_dashboard.groupby('Disciplina').agg(
                Total_Questoes=('Qsts', 'sum'),
                Total_Acertos=('Acertos', 'sum'),
                # CORREÇÃO AQUI: Usar '%' em vez de 'p'
                Media_Performance=('%', 'mean'),
                Total_Topicos=('ID', 'count')
            ).reset_index()

            # Calcula a performance geral e o progresso
            relatorio_disciplina['Performance Geral (%)'] = (relatorio_disciplina['Total_Acertos'] / relatorio_disciplina['Total_Questoes'] * 100).fillna(0)
            
            topicos_medidos = df_dashboard[df_dashboard['Domínio'] != '[Não Medido]'].groupby('Disciplina')['ID'].count().reset_index().rename(columns={'ID': 'Tópicos Medidos'})
            relatorio_final = pd.merge(relatorio_disciplina, topicos_medidos, on='Disciplina', how='left').fillna(0)

            relatorio_final['Progresso da Medição (%)'] = (relatorio_final['Tópicos Medidos'] / relatorio_final['Total_Topicos'] * 100).fillna(0)
            
            st.dataframe(relatorio_final, use_container_width=True, hide_index=True,
                         column_config={
                             "Performance Geral (%)": st.column_config.ProgressColumn(format="%.2f%%", min_value=0, max_value=100),
                             "Media_Performance": st.column_config.NumberColumn(label="Média de Performance (%)", format="%.2f%%"),
                             "Progresso da Medição (%)": st.column_config.ProgressColumn(format="%.2f%%", min_value=0, max_value=100)
                         })

        # --- Aba 2: Atividade Diária ---
        with tab2:
            st.subheader("Relatório de Atividade Diária (Questões)")
            # Esta parte será implementada quando tivermos o histórico de questões
            st.info("Funcionalidade a ser implementada: Carregar o histórico de simulados para análise diária.")


        # --- Aba 3: Tempo de Estudo por Matéria ---
        with tab3:
            st.subheader("Tempo Total de Estudo por Matéria")
            df_tempo = carregar_historico_tempo_df(perfil)
            
            if df_tempo.empty:
                st.info("Ainda não há registros de tempo de estudo para este perfil.")
            else:
                # Agrupa por matéria e soma os minutos
                tempo_por_materia = df_tempo.groupby('Disciplina')['Tempo_Estudado_Minutos'].sum().reset_index()
                
                # APLICA A NOVA FUNÇÃO DE FORMATAÇÃO
                tempo_por_materia['Tempo Total'] = tempo_por_materia['Tempo_Estudado_Minutos'].apply(formatar_minutos)
                
                # Exibe a tabela formatada
                st.dataframe(
                    tempo_por_materia[['Disciplina', 'Tempo Total']],
                    use_container_width=True,
                    hide_index=True
                )

                # Gráfico
                st.subheader("Distribuição do Tempo de Estudo")
                st.bar_chart(tempo_por_materia.rename(columns={'Tempo_Estudado_Minutos': 'Minutos Estudados'}), x='Disciplina', y='Minutos Estudados')

else:
    st.warning("Por favor, selecione um perfil na página principal para começar.")
    st.page_link("app_gui.py", label="Ir para a Página Principal", icon="🏠")

