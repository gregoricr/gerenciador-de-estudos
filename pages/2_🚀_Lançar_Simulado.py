import streamlit as st
import pandas as pd
from firebase_admin import firestore
from datetime import datetime, date

# --- FUNÇÕES AUXILIARES ---

@st.cache_resource
def get_db_connection():
    """Obtém a conexão com o cliente do Firestore."""
    try:
        return firestore.client()
    except Exception as e:
        st.error(f"Erro ao obter conexão com o Firebase: {e}")
        return None

db = get_db_connection()

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

if 'perfil_selecionado' in st.session_state and st.session_state.perfil_selecionado:
    perfil = st.session_state.perfil_selecionado
    st.info(f"Lançando resultados para o concurso: **{perfil['nome']}**")

    # NOVA FUNCIONALIDADE: DATA OPCIONAL
    st.markdown("---")
    data_retroativa = st.checkbox("Lançar resultado com data retroativa?")
    data_selecionada = date.today()
    if data_retroativa:
        data_selecionada = st.date_input("Selecione a data do simulado:", value=date.today(), max_value=date.today())
    st.markdown("---")


    st.subheader("1. Selecione os Tópicos Avaliados")
    lista_topicos = carregar_topicos_do_perfil(perfil)
    
    if lista_topicos:
        opcoes_display = [topico['display'] for topico in lista_topicos]
        topicos_selecionados_display = st.multiselect(
            "Pode selecionar um ou mais tópicos:",
            options=opcoes_display,
            key="selecao_topicos"
        )

        if st.button("Próximo Passo: Inserir Resultados", disabled=not topicos_selecionados_display):
            st.session_state.mostrar_form_resultados = True
    else:
        st.info("Carregando tópicos...")

    if st.session_state.get('mostrar_form_resultados', False):
        with st.form("lancar_simulado_form"):
            st.subheader("2. Insira os Resultados")
            resultados = {}
            for topico_display in topicos_selecionados_display:
                id_topico = topico_display.split(" - ")[0]
                
                st.markdown(f"**Tópico: {topico_display}**")
                col1, col2 = st.columns(2)
                questoes = col1.number_input(f"Nº de Questões (ID {id_topico})", min_value=1, step=1, key=f"q_{id_topico}")
                acertos = col2.number_input(f"Nº de Acertos (ID {id_topico})", min_value=0, step=1, key=f"a_{id_topico}")
                resultados[id_topico] = {"questoes": questoes, "acertos": acertos}

            submitted = st.form_submit_button("Salvar Resultado", type="primary")

            if submitted:
                with st.spinner("Salvando resultados na nuvem..."):
                    try:
                        # Determina a data a ser usada, com base na seleção do usuário
                        data_simulado_obj = data_selecionada
                        data_simulado_str = data_simulado_obj.strftime('%d/%m/%Y')

                        colecao_dashboard = perfil['colecao_dashboard']
                        colecao_historico = perfil['colecao_historico']
                        
                        erros = False
                        for id_topico, data in resultados.items():
                            novas_questoes = data['questoes']
                            novos_acertos = data['acertos']

                            if novos_acertos > novas_questoes:
                                st.error(f"Erro no Tópico ID {id_topico}: O número de acertos não pode ser maior que o número de questões.")
                                erros = True
                                continue
                            
                            doc_ref = db.collection(colecao_dashboard).document(str(id_topico))
                            
                            @firestore.transactional
                            def update_in_transaction(transaction, doc_ref, n_questoes, n_acertos, data_str):
                                snapshot = doc_ref.get(transaction=transaction)
                                total_q_antigo = snapshot.get('Total_Questoes_Topico') or 0
                                total_a_antigo = snapshot.get('Total_Acertos_Topico') or 0
                                
                                novo_total_q = total_q_antigo + n_questoes
                                novo_total_a = total_a_antigo + n_acertos
                                
                                perc = (novo_total_a / novo_total_q * 100) if novo_total_q > 0 else 0
                                
                                if perc >= 90: dominio = '[Domínio Mestre]'
                                elif 80 <= perc < 90: dominio = '[Domínio Sólido]'
                                elif 65 <= perc < 80: dominio = '[Em Desenvolvimento]'
                                else: dominio = '[Revisão Urgente]'

                                transaction.update(doc_ref, {
                                    'Total_Questoes_Topico': novo_total_q,
                                    'Total_Acertos_Topico': novo_total_a,
                                    '%': perc,
                                    'Domínio': dominio,
                                    'Ultima_Medicao': data_str
                                })
                            
                            transaction = db.transaction()
                            update_in_transaction(transaction, doc_ref, novas_questoes, novos_acertos, data_simulado_str)
                            
                            db.collection(colecao_historico).add({
                                'ID_Topico': int(id_topico),
                                'Data': data_simulado_str,
                                'Total_Questoes': novas_questoes,
                                'Acertos': novos_acertos,
                                '%': (novos_acertos / novas_questoes * 100) if novas_questoes > 0 else 0
                            })

                        if not erros:
                            st.success("Resultados salvos com sucesso!")
                            st.balloons()
                            st.cache_data.clear() # Limpa o cache para que os outros painéis se atualizem
                            del st.session_state.mostrar_form_resultados

                    except Exception as e:
                        st.error(f"Ocorreu um erro ao salvar os dados: {e}")
else:
    st.warning("Por favor, selecione um perfil na página principal para começar.")
    st.page_link("app_gui.py", label="Ir para a Página Principal", icon="🏠")

