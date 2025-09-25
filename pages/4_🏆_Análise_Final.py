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

# Função para carregar perfis arquivados que têm nota final
@st.cache_data(ttl=300)
def carregar_perfis_para_analise():
    """Carrega todos os perfis arquivados que têm uma nota final registada."""
    if not db:
        return []
    try:
        perfis_ref = db.collection('perfis_concursos').where('status', '==', 'Arquivado').stream()
        perfis_elegiveis = []
        for perfil in perfis_ref:
            perfil_data = perfil.to_dict()
            if perfil_data.get('nota_final') is not None and perfil_data.get('estrutura_prova'):
                perfil_data['id_documento'] = perfil.id
                perfis_elegiveis.append(perfil_data)
        return perfis_elegiveis
    except Exception as e:
        st.error(f"Erro ao carregar perfis arquivados: {e}")
        return []

# Função para carregar o dashboard (a mesma da outra página, para consistência)
@st.cache_data(ttl=300)
def carregar_dashboard_df(_perfil):
    """Carrega os dados do dashboard de um perfil específico."""
    if not _perfil or not db:
        return pd.DataFrame()
    colecao_dashboard = _perfil.get('colecao_dashboard')
    docs = db.collection(colecao_dashboard).stream()
    df = pd.DataFrame([doc.to_dict() for doc in docs])
    df.rename(columns={'Total_Questoes_Topico': 'Qsts', 
                     'Total_Acertos_Topico': 'Acertos'}, inplace=True, errors='ignore')
    return df

# --- LÓGICA DA PÁGINA ---
st.set_page_config(page_title="Análise Final", page_icon="🏆", layout="wide")

st.markdown("# 🏆 Análise Final de Performance")
st.markdown("Compare o seu desempenho nos estudos com o resultado real da prova.")

perfis_analisaveis = carregar_perfis_para_analise()

if not perfis_analisaveis:
    st.info("Ainda não há concursos arquivados com nota final registada para analisar.")
    st.info("Para analisar, vá a 'Gerenciar Perfis', arquive um concurso e adicione a nota da prova.")
else:
    nomes_perfis = [f"{p['nome']} ({p['ano']})" for p in perfis_analisaveis]
    perfil_selecionado_nome = st.selectbox("Selecione um concurso para analisar:", options=nomes_perfis)

    if perfil_selecionado_nome:
        # Encontra o dicionário completo do perfil selecionado
        perfil_selecionado = next((p for p in perfis_analisaveis if f"{p['nome']} ({p['ano']})" == perfil_selecionado_nome), None)

        if perfil_selecionado:
            df_dashboard = carregar_dashboard_df(perfil_selecionado)
            
            if df_dashboard.empty:
                st.error("Não foi possível carregar os dados de estudo para este perfil.")
            else:
                st.subheader(f"Relatório Final: {perfil_selecionado['nome']}")

                estrutura_prova = perfil_selecionado.get('estrutura_prova', {})
                nota_real = perfil_selecionado.get('nota_final')
                
                resultados = []
                nota_simulada_total = 0.0

                for disciplina, dados_prova in estrutura_prova.items():
                    df_disciplina = df_dashboard[df_dashboard['Disciplina'] == disciplina]
                    
                    total_acertos_disciplina = df_disciplina['Acertos'].sum()
                    total_questoes_disciplina = df_disciplina['Qsts'].sum()

                    perf_estudos = (total_acertos_disciplina / total_questoes_disciplina * 100) if total_questoes_disciplina > 0 else 0
                    
                    num_questoes_prova = dados_prova.get('num_questoes', 0)
                    peso = dados_prova.get('peso', 1.0)
                    
                    pontuacao_maxima_disciplina = num_questoes_prova * peso
                    pontuacao_estimada = (perf_estudos / 100) * pontuacao_maxima_disciplina
                    nota_simulada_total += pontuacao_estimada

                    resultados.append({
                        'Disciplina': disciplina,
                        'Perf. Estudos (%)': f"{perf_estudos:.2f}",
                        'Pontuação Estimada': f"{pontuacao_estimada:.2f} / {pontuacao_maxima_disciplina:.2f}"
                    })

                df_relatorio = pd.DataFrame(resultados)
                
                st.dataframe(df_relatorio, hide_index=True, use_container_width=True)
                
                st.markdown("---")
                
                col1, col2 = st.columns(2)
                col1.metric("Nota Simulada Final (com base nos estudos)", f"{nota_simulada_total:.2f}")
                col2.metric("Nota Real na Prova", f"{nota_real:.2f}", delta=f"{nota_real - nota_simulada_total:.2f}")

