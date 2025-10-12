import streamlit as st
import pandas as pd
from firebase_admin import firestore
import plotly.express as px
from datetime import datetime, time

# --- FUNÇÕES AUXILIARES ---

@st.cache_resource
def get_db_connection():
    """Obtém a conexão com o cliente do Firestore."""
    try:
        return firestore.client()
    except Exception:
        return None

db = get_db_connection()

# --- FUNÇÕES DE CARREGAMENTO DE DADOS ---
@st.cache_data(ttl=300)
def carregar_dashboard_df(_perfil):
    """Carrega a tabela de performance de um perfil."""
    if not _perfil or not db:
        return pd.DataFrame()
    try:
        colecao_dashboard = _perfil.get('colecao_dashboard')
        docs = db.collection(colecao_dashboard).stream()
        lista_de_topicos = [doc.to_dict() for doc in docs]

        if not lista_de_topicos:
            return pd.DataFrame()

        df = pd.DataFrame(lista_de_topicos)
        df.rename(columns={
            'Total_Questoes_Topico': 'Qsts', 
            'Total_Acertos_Topico': 'Acertos', 
            'Ultima_Medicao': 'Últ. Medição'
        }, inplace=True, errors='ignore')

        colunas_finais = ['ID', 'Disciplina', 'Tópico do Edital', 'Teoria (T)', 'Qsts', 'Acertos', 'Domínio', '%', 'Últ. Medição']
        df = df.reindex(columns=colunas_finais)

        valores_padrao = {
            'Qsts': 0, 'Acertos': 0, '%': 0, 'ID': 0,
            'Disciplina': 'N/A', 'Tópico do Edital': '-', 'Teoria (T)': '[ ]',
            'Domínio': '[Não Medido]', 'Últ. Medição': '-'
        }
        df.fillna(value=valores_padrao, inplace=True)

        df['ID'] = pd.to_numeric(df['ID']).astype(int)
        df['Qsts'] = pd.to_numeric(df['Qsts']).astype(int)
        df['Acertos'] = pd.to_numeric(df['Acertos']).astype(int)
        df['%'] = pd.to_numeric(df['%'])

        df = df.sort_values(by='ID').reset_index(drop=True)
        return df
        
    except Exception as e:
        st.error(f"Erro ao carregar o dashboard: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_historico_tempo_df(_perfil):
    """Carrega o histórico de tempo de estudo de um perfil."""
    if not _perfil or not db:
        return pd.DataFrame()
    try:
        id_perfil = _perfil.get('id_documento')
        if not id_perfil: return pd.DataFrame()
        
        colecao_historico_tempo = f"historico_tempo_{id_perfil}"
        docs = db.collection(colecao_historico_tempo).stream()
        df = pd.DataFrame([doc.to_dict() for doc in docs])
        return df if not df.empty else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_historico_questoes_df(_perfil):
    """Carrega o histórico de questões de um perfil."""
    if not _perfil or not db:
        return pd.DataFrame()
    try:
        colecao_historico = _perfil.get('colecao_historico')
        if not colecao_historico: return pd.DataFrame()
        docs = db.collection(colecao_historico).stream()
        df = pd.DataFrame([doc.to_dict() for doc in docs])
        return df if not df.empty else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def formatar_minutos(total_minutos):
    """Converte um total de minutos para o formato 'Xh Ymin'."""
    if total_minutos is None or total_minutos < 0:
        return "N/A"
    horas = int(total_minutos // 60)
    minutos = int(total_minutos % 60)
    return f"{horas}h {minutos:02d}min"

# --- LÓGICA DA PÁGINA ---
st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")
st.markdown("# 📊 Dashboard de Performance")

if 'perfil_selecionado' in st.session_state and st.session_state.perfil_selecionado:
    perfil = st.session_state.perfil_selecionado
    st.info(f"Exibindo dados para o concurso: **{perfil['nome']}**")

    # Recarrega o perfil para obter os dados de meta mais recentes
    perfil_atualizado_ref = db.collection('perfis_concursos').document(perfil['id_documento']).get()
    if perfil_atualizado_ref.exists:
        perfil = perfil_atualizado_ref.to_dict()
        perfil['id_documento'] = perfil_atualizado_ref.id # Garante que o ID do documento está no perfil
    
    df_dashboard = carregar_dashboard_df(perfil)
    df_tempo = carregar_historico_tempo_df(perfil)
    df_questoes = carregar_historico_questoes_df(perfil)

    if not df_dashboard.empty:
        # --- SEÇÃO DE METAS SEMANAIS ---
        meta_semanal = perfil.get('meta_semanal')
        if meta_semanal:
            hoje = datetime.now()
            try:
                data_inicio = datetime.strptime(meta_semanal['data_inicio'], '%d/%m/%Y')
                data_fim = datetime.combine(datetime.strptime(meta_semanal['data_fim'], '%d/%m/%Y'), time.max)
                
                if data_inicio <= hoje <= data_fim:
                    st.subheader(f"🎯 Meta da Semana ({meta_semanal['data_inicio']} a {meta_semanal['data_fim']})")

                    # Cálculo do progresso das questões
                    questoes_objetivo = meta_semanal.get('questoes_objetivo', 0)
                    questoes_semana = 0
                    if not df_questoes.empty and 'Data' in df_questoes.columns:
                        df_questoes['Data_dt'] = pd.to_datetime(df_questoes['Data'], format='%d/%m/%Y', errors='coerce')
                        questoes_semana = df_questoes[df_questoes['Data_dt'].between(data_inicio, data_fim)]['Total_Questoes'].sum()
                    
                    progresso_questoes = (questoes_semana / questoes_objetivo * 100) if questoes_objetivo > 0 else 0
                    st.markdown(f"**Questões Resolvidas:** {int(questoes_semana)} de {questoes_objetivo}")
                    st.progress(progresso_questoes / 100)

                    # Cálculo do progresso do tempo
                    horas_objetivo = meta_semanal.get('horas_objetivo', 0)
                    minutos_objetivo = horas_objetivo * 60
                    tempo_semana_min = 0
                    if not df_tempo.empty and 'Data' in df_tempo.columns:
                        df_tempo['Data_dt'] = pd.to_datetime(df_tempo['Data'], format='%d/%m/%Y', errors='coerce')
                        tempo_semana_min = df_tempo[df_tempo['Data_dt'].between(data_inicio, data_fim)]['Tempo_Estudado_Minutos'].sum()

                    progresso_tempo = (tempo_semana_min / minutos_objetivo * 100) if minutos_objetivo > 0 else 0
                    st.markdown(f"**Tempo de Estudo:** {formatar_minutos(tempo_semana_min)} de {horas_objetivo}h 00min")
                    st.progress(progresso_tempo / 100)

                    st.markdown("---")
            except (ValueError, TypeError):
                 st.warning("A meta semanal atual tem um formato de data inválido. Por favor, defina uma nova meta.")


        # --- CÁLCULO DOS KPIs ---
        total_questoes = df_dashboard['Qsts'].sum()
        total_acertos = df_dashboard['Acertos'].sum()
        performance_geral = (total_acertos / total_questoes * 100) if total_questoes > 0 else 0
        
        total_topicos = len(df_dashboard)
        topicos_medidos = len(df_dashboard[df_dashboard['Domínio'] != '[Não Medido]'])
        progresso_edital = (topicos_medidos / total_topicos * 100) if total_topicos > 0 else 0
        
        tempo_total_estudo_min = df_tempo['Tempo_Estudado_Minutos'].sum() if not df_tempo.empty else 0

        # --- EXIBIÇÃO DOS KPIs ---
        st.subheader("Visão Geral do Progresso")
        kpi_cols = st.columns(4)
        kpi_cols[0].metric(label="**Performance Geral**", value=f"{performance_geral:.2f}%")
        kpi_cols[1].metric(label="**Progresso do Edital**", value=f"{progresso_edital:.1f}%", help="Percentagem de tópicos medidos pelo menos uma vez.")
        kpi_cols[2].metric(label="**Volume de Questões**", value=f"{int(total_questoes)}")
        kpi_cols[3].metric(label="**Tempo Total de Estudo**", value=formatar_minutos(tempo_total_estudo_min))

        st.markdown("---")

        # --- GRÁFICOS ---
        st.subheader("Análise Visual")
        chart_cols = st.columns(2)
        with chart_cols[0]:
            df_dominio = df_dashboard['Domínio'].value_counts().reset_index()
            df_dominio.columns = ['Domínio', 'Contagem']
            fig = px.pie(df_dominio, values='Contagem', names='Domínio', 
                         title='Distribuição por Nível de Domínio', hole=.4,
                         color='Domínio',
                         color_discrete_map={
                             '[Domínio Mestre]': 'green',
                             '[Domínio Sólido]': 'royalblue',
                             '[Em Desenvolvimento]': 'orange',
                             '[Revisão Urgente]': 'red',
                             '[Não Medido]': 'grey'
                         })
            st.plotly_chart(fig, use_container_width=True)

        with chart_cols[1]:
            if not df_tempo.empty:
                tempo_por_materia = df_tempo.groupby('Disciplina')['Tempo_Estudado_Minutos'].sum().reset_index()
                fig_tempo = px.bar(tempo_por_materia, x='Disciplina', y='Tempo_Estudado_Minutos',
                                   title='Tempo de Estudo por Matéria (minutos)',
                                   labels={'Tempo_Estudado_Minutos': 'Minutos Estudados', 'Disciplina': 'Matéria'})
                st.plotly_chart(fig_tempo, use_container_width=True)
            else:
                st.info("Registe o seu tempo de estudo para ver a distribuição por matéria.")


        st.markdown("---")
        # --- TABELA DETALHADA COM FILTRO ---
        st.subheader("Análise Detalhada por Tópico")
        
        disciplinas = ["Todas"] + sorted(df_dashboard['Disciplina'].unique().tolist())
        disciplina_selecionada = st.selectbox("Filtrar por Disciplina:", options=disciplinas)

        df_filtrado = df_dashboard
        if disciplina_selecionada != "Todas":
            df_filtrado = df_dashboard[df_dashboard['Disciplina'] == disciplina_selecionada]

        st.dataframe(df_filtrado, use_container_width=True, hide_index=True)

    else:
        st.warning("Ainda não há dados no dashboard para este perfil.")
else:
    st.warning("Por favor, selecione um perfil na página principal para começar.")
    st.page_link("app_gui.py", label="Ir para a Página Principal", icon="🏠")

