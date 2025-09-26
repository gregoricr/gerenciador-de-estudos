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

@st.cache_data(ttl=300)
def carregar_topicos_do_perfil(_perfil):
    """Carrega a lista de todos os tópicos de um perfil."""
    if not _perfil or not db:
        return []
    try:
        colecao_dashboard = _perfil.get('colecao_dashboard')
        docs = db.collection(colecao_dashboard).order_by("ID").stream()
        topicos = [{"id": int(doc.to_dict().get('ID')), "display": f"{doc.to_dict().get('ID')} - {doc.to_dict().get('Tópico do Edital')}"} for doc in docs]
        return topicos
    except Exception as e:
        st.error(f"Erro ao carregar tópicos do Firebase: {e}")
        return []

@st.cache_data(ttl=300)
def carregar_historico_topico(_perfil, id_topico):
    """Carrega o histórico de lançamentos para um tópico específico."""
    if not _perfil or not db or not id_topico:
        return pd.DataFrame()
    try:
        colecao_historico = _perfil.get('colecao_historico')
        docs = db.collection(colecao_historico).where('ID_Topico', '==', id_topico).stream()
        
        registros = []
        for doc in docs:
            registro = doc.to_dict()
            registro['id_documento_historico'] = doc.id
            registros.append(registro)

        if not registros:
            return pd.DataFrame()

        df = pd.DataFrame(registros)
        # Converte a data para um formato ordenável e depois formata para exibição
        df['Data'] = pd.to_datetime(df['Data'], format='%d/%m/%Y', errors='coerce')
        df = df.sort_values(by='Data', ascending=False)
        df['Data'] = df['Data'].dt.strftime('%d/%m/%Y')
        return df

    except Exception as e:
        st.error(f"Erro ao carregar o histórico do tópico: {e}")
        return pd.DataFrame()

def get_nivel_dominio(percentual):
    if percentual >= 90: return '[Domínio Mestre]'
    elif 80 <= percentual < 90: return '[Domínio Sólido]'
    elif 65 <= percentual < 80: return '[Em Desenvolvimento]'
    else: return '[Revisão Urgente]'

# --- LÓGICA DA PÁGINA ---
st.set_page_config(page_title="Gerenciar Histórico", page_icon="🗂️", layout="wide")

st.markdown("# 🗂️ Gerenciar Histórico de Lançamentos")
st.markdown("Visualize o histórico detalhado de um tópico e apague registros incorretos.")

if 'perfil_selecionado' in st.session_state and st.session_state.perfil_selecionado:
    perfil = st.session_state.perfil_selecionado
    st.info(f"A gerenciar o histórico para o concurso: **{perfil['nome']}**")

    topicos = carregar_topicos_do_perfil(perfil)
    if topicos:
        opcoes_display = [topico['display'] for topico in topicos]
        
        topico_selecionado_display = st.selectbox(
            "Selecione o tópico que deseja analisar:",
            options=opcoes_display,
            index=None,
            placeholder="Escolha um tópico..."
        )

        if topico_selecionado_display:
            id_topico_selecionado = int(topico_selecionado_display.split(" - ")[0])
            
            df_historico_topico = carregar_historico_topico(perfil, id_topico_selecionado)

            if df_historico_topico.empty:
                st.warning("Ainda não há lançamentos no histórico para este tópico.")
            else:
                st.subheader(f"Histórico de: {topico_selecionado_display}")
                
                # Exibe cada registro com um botão de apagar
                for index, row in df_historico_topico.iterrows():
                    with st.container(border=True):
                        col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 1])
                        col1.metric("Data", row['Data'])
                        col2.metric("Nº de Questões", f"{row['Total_Questoes']:.0f}")
                        col3.metric("Nº de Acertos", f"{row['Acertos']:.0f}")
                        col4.metric("Performance", f"{row['%']:.2f}%")
                        
                        if col5.button("Apagar", key=row['id_documento_historico'], type="secondary"):
                            
                            with st.spinner("A apagar registro e a recalcular performance..."):
                                try:
                                    # Dados a serem subtraídos
                                    questoes_a_remover = row['Total_Questoes']
                                    acertos_a_remover = row['Acertos']
                                    id_doc_historico = row['id_documento_historico']
                                    
                                    # Referências dos documentos
                                    doc_ref_historico = db.collection(perfil['colecao_historico']).document(id_doc_historico)
                                    doc_ref_dashboard = db.collection(perfil['colecao_dashboard']).document(str(id_topico_selecionado))
                                    
                                    # Transação para garantir consistência
                                    @firestore.transactional
                                    def apagar_e_atualizar(transaction, ref_dashboard, ref_historico, q_remover, a_remover):
                                        # 1. Lê o estado atual do dashboard
                                        snapshot_dashboard = ref_dashboard.get(transaction=transaction)
                                        total_q_antigo = snapshot_dashboard.get('Total_Questoes_Topico') or 0
                                        total_a_antigo = snapshot_dashboard.get('Total_Acertos_Topico') or 0

                                        # 2. Calcula os novos totais
                                        novo_total_q = total_q_antigo - q_remover
                                        novo_total_a = total_a_antigo - a_remover
                                        
                                        # 3. Recalcula a performance
                                        novo_perc = (novo_total_a / novo_total_q * 100) if novo_total_q > 0 else 0.0
                                        novo_dominio = get_nivel_dominio(novo_perc) if novo_total_q > 0 else "[Não Medido]"

                                        # 4. Atualiza o dashboard
                                        transaction.update(ref_dashboard, {
                                            'Total_Questoes_Topico': novo_total_q,
                                            'Total_Acertos_Topico': novo_total_a,
                                            '%': novo_perc,
                                            'Domínio': novo_dominio
                                        })

                                        # 5. Apaga o registro do histórico
                                        transaction.delete(ref_historico)

                                    transaction = db.transaction()
                                    apagar_e_atualizar(transaction, doc_ref_dashboard, doc_ref_historico, questoes_a_remover, acertos_a_remover)
                                    
                                    st.success("Registro apagado com sucesso!")
                                    st.cache_data.clear() # Limpa todo o cache
                                    st.rerun()

                                except Exception as e:
                                    st.error(f"Ocorreu um erro ao apagar o registro: {e}")

    else:
        st.warning("Não foi possível carregar os tópicos do edital.")
else:
    st.warning("Por favor, selecione um perfil na página principal para começar.")
    st.page_link("app_gui.py", label="Ir para a Página Principal", icon="🏠")
