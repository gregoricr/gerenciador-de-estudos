import streamlit as st
from firebase_admin import firestore
from datetime import date
import pandas as pd

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
def get_disciplinas_from_dashboard(_perfil):
    """Obtém a lista de disciplinas únicas de um dashboard."""
    if not _perfil or not db:
        return []
    try:
        colecao_dashboard = _perfil.get('colecao_dashboard')
        docs = db.collection(colecao_dashboard).stream()
        df = pd.DataFrame([doc.to_dict() for doc in docs])
        if 'Disciplina' in df.columns and not df.empty:
            return sorted(df['Disciplina'].unique().tolist())
        return []
    except Exception:
        return []

# --- LÓGICA DA PÁGINA ---
st.set_page_config(page_title="Registrar Tempo de Estudo", page_icon="⏱️", layout="centered")

st.markdown("# ⏱️ Registrar Tempo de Estudo")

if 'perfil_selecionado' in st.session_state and st.session_state.perfil_selecionado:
    perfil = st.session_state.perfil_selecionado
    st.info(f"Registrando tempo de estudo para o concurso: **{perfil['nome']}**")

    # Seletor de data opcional
    data_retroativa = st.checkbox("Registrar tempo para uma data retroativa?")
    data_selecionada = date.today()
    if data_retroativa:
        data_selecionada = st.date_input("Selecione a data da sessão de estudo:", value=date.today(), max_value=date.today())

    st.markdown("---")
    
    with st.form("registrar_tempo_form"):
        st.subheader("Sessão de Estudo")

        # Seleção de Disciplinas (Matérias)
        lista_disciplinas = get_disciplinas_from_dashboard(perfil)
        
        if not lista_disciplinas:
            st.warning("Não foi possível carregar as disciplinas do perfil selecionado.")
        else:
            disciplina_selecionada = st.selectbox(
                "Selecione a matéria estudada nesta sessão:",
                options=lista_disciplinas
            )

            # Entrada de Tempo com limite de 6 horas
            st.markdown("**Tempo de estudo líquido**")
            col1, col2 = st.columns(2)
            horas = col1.number_input("Horas", min_value=0, max_value=6, value=1, step=1, help="Máximo de 6 horas por registro.")
            minutos = col2.number_input("Minutos", min_value=0, max_value=55, value=0, step=5, help="Intervalos de 5 minutos.")

            submitted = st.form_submit_button("Salvar Sessão de Estudo", type="primary")

            if submitted:
                tempo_total_minutos = (horas * 60) + minutos

                if not disciplina_selecionada or tempo_total_minutos == 0:
                    st.warning("Por favor, selecione uma matéria e insira um tempo de estudo válido.")
                elif horas == 6 and minutos > 0:
                     st.error("O tempo máximo de registro por sessão é de 6 horas.")
                else:
                    with st.spinner("Salvando sessão de estudo..."):
                        try:
                            # CORREÇÃO AQUI: Usa o 'id_documento' garantido pela sessão
                            id_perfil = perfil.get('id_documento')
                            if not id_perfil:
                                raise ValueError("ID do perfil não encontrado na sessão. Por favor, recarregue o perfil na página principal.")

                            colecao_historico_tempo = f"historico_tempo_{id_perfil}"
                            
                            data_sessao_str = data_selecionada.strftime('%d/%m/%Y')
                            
                            db.collection(colecao_historico_tempo).add({
                                'Disciplina': disciplina_selecionada,
                                'Data': data_sessao_str,
                                'Tempo_Estudado_Minutos': tempo_total_minutos
                            })

                            st.success(f"Sessão de estudo de {tempo_total_minutos} minutos em '{disciplina_selecionada}' registrada com sucesso!")
                            st.balloons()
                            # Limpa o cache para que o relatório seja atualizado
                            st.cache_data.clear()

                        except Exception as e:
                            st.error(f"Ocorreu um erro ao salvar a sessão: {e}")

else:
    st.warning("Por favor, selecione um perfil na página principal para começar.")
    st.page_link("app_gui.py", label="Ir para a Página Principal", icon="🏠")

