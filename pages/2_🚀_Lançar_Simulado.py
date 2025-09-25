import streamlit as st
import pandas as pd
from firebase_admin import firestore
from datetime import datetime
import time

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

# Função para carregar os tópicos de um perfil
@st.cache_data(ttl=300)
def carregar_topicos_do_perfil(_perfil):
    """Carrega a lista de tópicos de um perfil específico para o seletor."""
    if not _perfil or not db:
        return []
    
    colecao_dashboard = _perfil.get('colecao_dashboard')
    if not colecao_dashboard:
        st.error("Informação da coleção do dashboard não encontrada no perfil.")
        return []

    try:
        docs = db.collection(colecao_dashboard).order_by("ID").stream()
        topicos = [{"id": doc.id, "display": f"{doc.to_dict().get('ID')} - {doc.to_dict().get('Tópico do Edital')}"} for doc in docs]
        return topicos
    except Exception as e:
        st.error(f"Erro ao carregar tópicos do Firebase: {e}")
        return []

# --- LÓGICA DA PÁGINA ---
st.set_page_config(page_title="Lançar Simulado", page_icon="🚀", layout="centered")

st.markdown("# 🚀 Lançar Resultado de Simulado")

# Inicializa o estado da sessão para guardar os tópicos selecionados
if 'topicos_para_lancamento' not in st.session_state:
    st.session_state.topicos_para_lancamento = []

if 'perfil_selecionado' in st.session_state and st.session_state.perfil_selecionado:
    perfil = st.session_state.perfil_selecionado
    st.info(f"Lançando resultados para o concurso: **{perfil['nome']}**")

    # --- ETAPA 1: Seleção de Tópicos (Fora do Formulário) ---
    if not st.session_state.topicos_para_lancamento:
        st.markdown("### 1. Selecione os Tópicos Avaliados")
        lista_topicos = carregar_topicos_do_perfil(perfil)
        
        if lista_topicos:
            opcoes_display = [topico['display'] for topico in lista_topicos]
            topicos_selecionados_display = st.multiselect(
                "Pode selecionar um ou mais tópicos:",
                options=opcoes_display,
                key="topicos_multiselect"
            )

            if st.button("Próximo Passo: Inserir Resultados", disabled=not topicos_selecionados_display):
                st.session_state.topicos_para_lancamento = topicos_selecionados_display
                st.rerun()
        else:
            st.info("A carregar tópicos...")

    # --- ETAPA 2: Formulário de Inserção (Apenas se houver tópicos selecionados) ---
    if st.session_state.topicos_para_lancamento:
        with st.form("lancar_simulado_form"):
            st.markdown("### 2. Insira os Resultados")
            resultados = {}
            for topico_display in st.session_state.topicos_para_lancamento:
                id_topico = topico_display.split(" - ")[0]
                st.markdown(f"**Tópico:** {topico_display}")
                col1, col2 = st.columns(2)
                questoes = col1.number_input(f"Nº de Questões (ID {id_topico})", min_value=1, step=1, key=f"q_{id_topico}")
                acertos = col2.number_input(f"Nº de Acertos (ID {id_topico})", min_value=0, step=1, key=f"a_{id_topico}")
                resultados[id_topico] = {"questoes": questoes, "acertos": acertos}

            # Botões de submissão e cancelamento
            submitted, cancelled = st.columns([1,1])[0].form_submit_button("Salvar Resultado Final", type="primary"), st.columns([1,1])[1].form_submit_button("Cancelar")

            if submitted:
                # Lógica para guardar os dados (mantida da versão anterior)
                colecao_dashboard = perfil['colecao_dashboard']
                colecao_historico = perfil['colecao_historico']
                erros = []
                
                with st.spinner("A guardar resultados na nuvem..."):
                    for id_topico, data in resultados.items():
                        if data['acertos'] > data['questoes']:
                            erros.append(f"Tópico ID {id_topico}: O número de acertos não pode ser maior que o de questões.")
                    
                    if not erros:
                        try:
                            # Lógica de transação e adição ao histórico...
                            for id_topico, data in resultados.items():
                                doc_ref = db.collection(colecao_dashboard).document(str(id_topico))
                                @firestore.transactional
                                def update_in_transaction(transaction, doc_ref, n_questoes, n_acertos):
                                    snapshot = doc_ref.get(transaction=transaction)
                                    total_q_antigo, total_a_antigo = snapshot.get('Total_Questoes_Topico') or 0, snapshot.get('Total_Acertos_Topico') or 0
                                    novo_total_q, novo_total_a = total_q_antigo + n_questoes, total_a_antigo + n_acertos
                                    perc = (novo_total_a / novo_total_q * 100) if novo_total_q > 0 else 0
                                    
                                    if perc >= 90: dominio = '[Domínio Mestre]'
                                    elif 80 <= perc < 90: dominio = '[Domínio Sólido]'
                                    elif 65 <= perc < 80: dominio = '[Em Desenvolvimento]'
                                    else: dominio = '[Revisão Urgente]'
                                    
                                    transaction.update(doc_ref, {'Total_Questoes_Topico': novo_total_q, 'Total_Acertos_Topico': novo_total_a, '%': perc, 'Domínio': dominio, 'Ultima_Medicao': datetime.now().strftime('%d/%m/%Y')})
                                
                                transaction = db.transaction()
                                update_in_transaction(transaction, doc_ref, data['questoes'], data['acertos'])
                                
                                db.collection(colecao_historico).add({'ID_Topico': int(id_topico), 'Data': datetime.now().strftime('%d/%m/%Y'), 'Total_Questoes': data['questoes'], 'Acertos': data['acertos'], '%': (data['acertos'] / data['questoes'] * 100) if data['questoes'] > 0 else 0})
                            
                            st.success("Resultados guardados com sucesso!")
                            st.balloons()
                            st.cache_data.clear()
                            st.session_state.topicos_para_lancamento = []
                            time.sleep(1.5)
                            st.rerun()

                        except Exception as e:
                            st.error(f"Ocorreu um erro ao guardar os dados: {e}")
                    else:
                        for erro in erros: st.error(erro)

            if cancelled:
                st.session_state.topicos_para_lancamento = []
                st.rerun()
else:
    st.warning("Por favor, selecione um perfil na página principal para começar.")
    st.page_link("app_principal.py", label="Ir para a Página Principal", icon="🏠")

