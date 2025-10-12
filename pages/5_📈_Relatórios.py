import streamlit as st
import pandas as pd
from firebase_admin import firestore
from datetime import datetime, timedelta

# --- FUNÇÕES AUXILIARES ---

@st.cache_resource
def get_db_connection():
    """Obtém a conexão com o cliente do Firestore."""
    try:
        return firestore.client()
    except Exception:
        return None

db = get_db_connection()

# Funções de carregamento de dados
@st.cache_data(ttl=300)
def carregar_dashboard_df(_perfil):
    if not _perfil or not db: return pd.DataFrame()
    try:
        docs = db.collection(_perfil.get('colecao_dashboard')).stream()
        return pd.DataFrame([doc.to_dict() for doc in docs])
    except Exception: return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_historico_tempo_df(_perfil):
    if not _perfil or not db: return pd.DataFrame()
    try:
        docs = db.collection(f"historico_tempo_{_perfil.get('id_documento')}").stream()
        df = pd.DataFrame([doc.to_dict() for doc in docs])
        if not df.empty and 'Data' in df.columns:
            df['Data_dt'] = pd.to_datetime(df['Data'], format='%d/%m/%Y', errors='coerce')
        return df
    except Exception: return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_historico_questoes_df(_perfil):
    if not _perfil or not db: return pd.DataFrame()
    try:
        docs = db.collection(_perfil.get('colecao_historico')).stream()
        df = pd.DataFrame([doc.to_dict() for doc in docs])
        if not df.empty and 'Data' in df.columns:
            df['Data_dt'] = pd.to_datetime(df['Data'], format='%d/%m/%Y', errors='coerce')
        return df
    except Exception: return pd.DataFrame()

def formatar_minutos(total_minutos):
    if total_minutos is None or total_minutos < 0: return "N/A"
    horas = int(total_minutos // 60)
    minutos = int(total_minutos % 60)
    return f"{horas}h {minutos:02d}min"

# --- LÓGICA DA PÁGINA ---
st.set_page_config(page_title="Relatórios", page_icon="📈", layout="wide")

st.markdown("# 📈 Relatórios Analíticos")
st.markdown("Analise seu progresso com visões consolidadas do seu desempenho.")

if 'perfil_selecionado' in st.session_state and st.session_state.perfil_selecionado:
    perfil = st.session_state.perfil_selecionado
    st.info(f"Exibindo relatórios para o concurso: **{perfil['nome']}**")

    # --- CARREGAMENTO INICIAL DOS DADOS ---
    df_dashboard_total = carregar_dashboard_df(perfil)
    df_tempo_total = carregar_historico_tempo_df(perfil)
    df_questoes_total = carregar_historico_questoes_df(perfil)

    # --- NOVO SELETOR DE PERÍODO ---
    st.sidebar.title("Filtro Temporal")
    periodo_selecionado = st.sidebar.selectbox(
        "Selecione o período de análise:",
        options=[
            "Todo o período", "Últimos 7 dias", "Últimos 14 dias", 
            "Últimos 21 dias", "Último mês", "Últimos 2 meses", "Últimos 3 meses"
        ],
        index=0
    )

    # --- LÓGICA DE FILTRAGEM ---
    hoje = datetime.now()
    data_inicio = None

    if periodo_selecionado == "Últimos 7 dias":
        data_inicio = hoje - timedelta(days=7)
    elif periodo_selecionado == "Últimos 14 dias":
        data_inicio = hoje - timedelta(days=14)
    elif periodo_selecionado == "Últimos 21 dias":
        data_inicio = hoje - timedelta(days=21)
    elif periodo_selecionado == "Último mês":
        data_inicio = hoje - timedelta(days=30)
    elif periodo_selecionado == "Últimos 2 meses":
        data_inicio = hoje - timedelta(days=60)
    elif periodo_selecionado == "Últimos 3 meses":
        data_inicio = hoje - timedelta(days=90)

    # Filtra os dataframes de histórico
    if data_inicio:
        df_tempo = df_tempo_total[df_tempo_total['Data_dt'] >= data_inicio] if not df_tempo_total.empty else pd.DataFrame()
        df_questoes = df_questoes_total[df_questoes_total['Data_dt'] >= data_inicio] if not df_questoes_total.empty else pd.DataFrame()
    else: # "Todo o período"
        df_tempo = df_tempo_total
        df_questoes = df_questoes_total

    # ATENÇÃO: Os KPIs do dashboard (Total_Questoes_Topico, etc) refletem o total.
    # Para o relatório de performance por disciplina, vamos recalcular com base no histórico filtrado.
    df_dashboard = df_dashboard_total.copy()


    if df_dashboard.empty:
        st.warning("Não há dados de dashboard para este perfil. Lance um simulado para começar a ver os relatórios.")
    else:
        # --- PAINEL DE CONTROLE GERAL (KPIs) ---
        # Estes KPIs sempre mostram o total, não são afetados pelo filtro de período
        st.subheader(f"Painel de Controle Geral ({periodo_selecionado})")
        
        # Cálculos dos KPIs baseados nos dados FILTRADOS
        total_questoes_periodo = df_questoes['Total_Questoes'].sum() if not df_questoes.empty else 0
        total_acertos_periodo = df_questoes['Acertos'].sum() if not df_questoes.empty else 0
        performance_periodo = (total_acertos_periodo / total_questoes_periodo * 100) if total_questoes_periodo > 0 else 0
        
        tempo_total_periodo_min = df_tempo['Tempo_Estudado_Minutos'].sum() if not df_tempo.empty else 0
        
        media_diaria_min = 0
        if not df_tempo.empty and 'Data_dt' in df_tempo.columns:
            dias_de_estudo = df_tempo['Data_dt'].dropna().dt.date.nunique()
            if dias_de_estudo > 0:
                media_diaria_min = tempo_total_periodo_min / dias_de_estudo
        
        progresso_edital = (len(df_dashboard[df_dashboard['Domínio'] != '[Não Medido]']) / len(df_dashboard) * 100) if not df_dashboard.empty else 0

        kpi_cols = st.columns(5)
        kpi_cols[0].metric("Performance no Período", f"{performance_periodo:.2f}%")
        kpi_cols[1].metric("Progresso Total do Edital", f"{progresso_edital:.1f}%")
        kpi_cols[2].metric("Questões no Período", f"{int(total_questoes_periodo)}")
        kpi_cols[3].metric("Horas no Período", formatar_minutos(tempo_total_periodo_min))
        kpi_cols[4].metric("Média Diária no Período", formatar_minutos(media_diaria_min))
        
        st.markdown("---")

        # --- ABAS COM RELATÓRIOS DETALHADOS ---
        tab1, tab2, tab3 = st.tabs(["Performance por Disciplina", "Atividade Diária", "Tempo de Estudo por Matéria"])

        # Aba 1: Performance por Disciplina (agora usa dados filtrados)
        with tab1:
            st.subheader(f"Performance por Disciplina ({periodo_selecionado})")
            if df_questoes.empty:
                st.info("Sem dados de questões para o período selecionado.")
            else:
                # Recalcula a performance com base nos tópicos do dashboard e no histórico de questões filtrado
                performance_disciplina = df_questoes.groupby(df_questoes['ID_Topico'].map(df_dashboard.set_index('ID')['Disciplina'])).agg(
                    Total_Questoes=('Total_Questoes', 'sum'),
                    Total_Acertos=('Acertos', 'sum')
                ).reset_index().rename(columns={'ID_Topico': 'Disciplina'})

                performance_disciplina['Performance Geral (%)'] = (performance_disciplina['Total_Acertos'] / performance_disciplina['Total_Questoes'] * 100).fillna(0)
                
                st.dataframe(performance_disciplina, use_container_width=True, hide_index=True,
                             column_config={
                                 "Performance Geral (%)": st.column_config.ProgressColumn(format="%.2f%%", min_value=0, max_value=100)
                             })

        # Aba 2: Atividade Diária
        with tab2:
            st.subheader(f"Atividade Diária ({periodo_selecionado})")
            if df_questoes.empty or 'Data_dt' not in df_questoes.columns:
                st.info("Ainda não há registros de simulados para o período selecionado.")
            else:
                atividade_diaria = df_questoes.groupby(df_questoes['Data_dt'].dt.date).agg(
                    Total_Questoes=('Total_Questoes', 'sum'),
                    Acertos=('Acertos', 'sum')
                ).reset_index()
                atividade_diaria['Performance (%)'] = (atividade_diaria['Acertos'] / atividade_diaria['Total_Questoes'] * 100).fillna(0)
                atividade_diaria.rename(columns={'Data_dt': 'Data'}, inplace=True)
                
                st.dataframe(atividade_diaria.sort_values(by='Data', ascending=False), use_container_width=True, hide_index=True)
                
                st.subheader("Volume de Questões por Dia")
                st.bar_chart(atividade_diaria.rename(columns={'Data': 'index'}).set_index('index'), y='Total_Questoes')

        # Aba 3: Tempo de Estudo por Matéria
        with tab3:
            st.subheader(f"Tempo de Estudo por Matéria ({periodo_selecionado})")
            if df_tempo.empty:
                st.info("Ainda não há registros de tempo de estudo para o período selecionado.")
            else:
                tempo_por_materia = df_tempo.groupby('Disciplina')['Tempo_Estudado_Minutos'].sum().reset_index()
                tempo_por_materia['Tempo Total'] = tempo_por_materia['Tempo_Estudado_Minutos'].apply(formatar_minutos)
                
                df_para_exibir = tempo_por_materia.sort_values(by='Tempo_Estudado_Minutos', ascending=False)
                
                st.dataframe(
                    df_para_exibir[['Disciplina', 'Tempo Total']],
                    use_container_width=True,
                    hide_index=True
                )
                
                st.subheader("Distribuição do Tempo de Estudo")
                st.bar_chart(tempo_por_materia.rename(columns={'Tempo_Estudado_Minutos': 'Minutos Estudados'}), x='Disciplina', y='Minutos Estudados')

else:
    st.warning("Por favor, selecione um perfil na página principal para começar.")
    st.page_link("app_gui.py", label="Ir para a Página Principal", icon="🏠")

