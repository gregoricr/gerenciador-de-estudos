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
        # Garante que a coluna 'ID' é numérica para ordenação
        df['ID'] = pd.to_numeric(df['ID'], errors='coerce')
        df.sort_values(by='ID', inplace=True)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar o dashboard: {e}")
        return pd.DataFrame()

# --- LÓGICA DA PÁGINA ---
st.set_page_config(page_title="Estudo Teórico", page_icon="📖", layout="centered")

st.markdown("# 📖 Registro de Estudo Teórico")
st.markdown("Marque os tópicos do edital cuja teoria já concluiu.")

if 'perfil_selecionado' in st.session_state and st.session_state.perfil_selecionado:
    perfil = st.session_state.perfil_selecionado
    st.info(f"A gerir o estudo teórico para o concurso: **{perfil['nome']}**")

    df_dashboard = carregar_dashboard_df(perfil)

    if not df_dashboard.empty:
        # Filtra apenas os tópicos que ainda não foram marcados como estudados
        topicos_pendentes = df_dashboard[df_dashboard['Teoria (T)'] == '[ ]']

        if topicos_pendentes.empty:
            st.success("🎉 Parabéns! Já concluiu o estudo teórico de todos os tópicos deste edital.")
            st.balloons()
        else:
            opcoes_display = [
                f"{row['ID']} - {row['Tópico do Edital']} ({row['Disciplina']})"
                for index, row in topicos_pendentes.iterrows()
            ]

            with st.form("form_estudo_teorico"):
                st.write("Selecione os tópicos que concluiu:")
                topicos_selecionados_display = st.multiselect(
                    "Pode selecionar um ou mais tópicos:",
                    options=opcoes_display,
                    label_visibility="collapsed"
                )

                submitted = st.form_submit_button("Marcar Selecionados como Estudados", type="primary")

                if submitted:
                    if not topicos_selecionados_display:
                        st.warning("Nenhum tópico foi selecionado.")
                    else:
                        ids_para_marcar = [
                            display.split(" - ")[0] for display in topicos_selecionados_display
                        ]
                        
                        with st.spinner("A atualizar o seu progresso na nuvem..."):
                            try:
                                colecao_dashboard = perfil.get('colecao_dashboard')
                                batch = db.batch()
                                
                                for id_topico in ids_para_marcar:
                                    doc_ref = db.collection(colecao_dashboard).document(str(id_topico))
                                    batch.update(doc_ref, {'Teoria (T)': '[X]'})
                                
                                batch.commit()
                                st.success(f"{len(ids_para_marcar)} tópico(s) marcado(s) com sucesso!")
                                
                                # Limpa o cache para recarregar os dados atualizados
                                st.cache_data.clear()
                                # Força o recarregamento da página para atualizar a lista
                                st.rerun()

                            except Exception as e:
                                st.error(f"Ocorreu um erro ao guardar as alterações: {e}")
    else:
        st.warning("Não foi possível carregar os tópicos. O dashboard parece estar vazio.")

else:
    st.warning("Por favor, selecione um perfil na página principal para começar.")
    st.page_link("app_gui.py", label="Ir para a Página Principal", icon="🏠")

