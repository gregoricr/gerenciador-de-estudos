import streamlit as st
import pandas as pd
from firebase_admin import firestore
import os
from datetime import datetime

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
def carregar_todos_perfis():
    """Carrega todos os perfis de concurso do banco de dados."""
    if not db:
        return {}
    try:
        perfis_ref = db.collection('perfis_concursos').stream()
        perfis = {}
        for doc in perfis_ref:
            perfil_data = doc.to_dict()
            perfil_data['id_documento'] = doc.id
            perfis[doc.id] = perfil_data
        # Ordena os perfis para uma exibição consistente
        perfis_ordenados = dict(sorted(perfis.items(), key=lambda item: (item[1]['status'], item[1]['nome'])))
        return perfis_ordenados
    except Exception as e:
        st.error(f"Erro ao carregar perfis: {e}")
        return {}

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
            return df['Disciplina'].unique().tolist()
        return []
    except Exception:
        return []

# --- LÓGICA DA PÁGINA ---
st.set_page_config(page_title="Gerenciar Perfis", page_icon="⚙️", layout="centered")

st.markdown("# ⚙️ Gerenciar Perfis")
st.markdown("Crie novos perfis de estudo ou gerencie o status dos concursos existentes.")

tab1, tab2 = st.tabs(["Gerenciar Status", "Criar Novo Perfil"])

# --- Aba de Gestão de Status ---
with tab1:
    st.subheader("Gerenciar Concursos Existentes")
    
    perfis = carregar_todos_perfis()

    if not perfis:
        st.info("Nenhum perfil de concurso encontrado. Crie um na aba ao lado.")
    else:
        for perfil_id, perfil in perfis.items():
            with st.container(border=True):
                col_info, col_action = st.columns([2, 1])
                
                with col_info:
                    st.markdown(f"**{perfil['nome']}** ({perfil['ano']})")
                    nota_final_str = f"{perfil.get('nota_final', 'N/A'):.2f}" if isinstance(perfil.get('nota_final'), (int, float)) else "Não registrada"
                    st.caption(f"Status: **{perfil['status']}** | Nota Final: **{nota_final_str}**")

                with col_action:
                    if perfil['status'] == 'Ativo':
                        if st.button("Arquivar", key=f"archive_{perfil_id}", use_container_width=True):
                            st.session_state.perfil_para_arquivar = perfil
                            st.rerun()
                    else: # Arquivado
                        sub_cols = st.columns(3)
                        with sub_cols[0]:
                            if st.button("Reativar", key=f"reactivate_{perfil_id}", use_container_width=True):
                                try:
                                    db.collection('perfis_concursos').document(perfil_id).update({'status': 'Ativo'})
                                    st.success(f"Perfil '{perfil['nome']}' reativado!")
                                    st.cache_data.clear()
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao reativar: {e}")
                        with sub_cols[1]:
                            if st.button("Nota", key=f"edit_nota_{perfil_id}", use_container_width=True):
                                st.session_state.perfil_para_editar_nota = perfil
                                st.rerun()
                        with sub_cols[2]:
                            if st.button("Estrutura", key=f"edit_estrutura_{perfil_id}", use_container_width=True):
                                st.session_state.perfil_para_editar_estrutura = perfil
                                st.rerun()
    
    # --- Formulários de Ação (Renderizados condicionalmente fora do loop) ---
    
    # Formulário para ARQUIVAR um perfil
    if 'perfil_para_arquivar' in st.session_state and st.session_state.perfil_para_arquivar:
        perfil = st.session_state.perfil_para_arquivar
        with st.form(key=f"form_arquivar_{perfil['id_documento']}"):
            st.warning(f"Arquivando: **{perfil['nome']}**")
            registra_nota = st.checkbox("Registrar a nota final da prova", value=False)
            nota_final = None
            if registra_nota:
                nota_final = st.number_input("Digite a nota final (ex: 85.75):", format="%.2f", step=0.01)
            
            submitted = st.form_submit_button("Confirmar Arquivamento")
            if submitted:
                with st.spinner("Arquivando..."):
                    try:
                        db.collection('perfis_concursos').document(perfil['id_documento']).update({'status': 'Arquivado', 'nota_final': nota_final})
                        st.success("Perfil arquivado com sucesso!")
                        del st.session_state.perfil_para_arquivar
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao arquivar: {e}")

    # Formulário para EDITAR NOTA de um perfil arquivado
    if 'perfil_para_editar_nota' in st.session_state and st.session_state.perfil_para_editar_nota:
        perfil = st.session_state.perfil_para_editar_nota
        with st.form(key=f"form_edit_nota_{perfil['id_documento']}"):
            st.info(f"Editando a nota final para: **{perfil['nome']}**")
            nota_atual = perfil.get('nota_final') or 0.0
            nova_nota = st.number_input("Digite a nova nota final:", value=float(nota_atual), format="%.2f", step=0.01)
            
            submitted = st.form_submit_button("Salvar Nota")
            if submitted:
                with st.spinner("Salvando nota..."):
                    try:
                        db.collection('perfis_concursos').document(perfil['id_documento']).update({'nota_final': nova_nota})
                        st.success("Nota salva com sucesso!")
                        del st.session_state.perfil_para_editar_nota
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar a nota: {e}")

    # Formulário para EDITAR ESTRUTURA da prova
    if 'perfil_para_editar_estrutura' in st.session_state:
        perfil = st.session_state.perfil_para_editar_estrutura
        disciplinas = get_disciplinas_from_dashboard(perfil)
        if disciplinas:
            with st.form(key=f"form_edit_estrutura_{perfil['id_documento']}"):
                st.info(f"Editando a Estrutura da Prova para: **{perfil['nome']}**")
                estrutura_atual = perfil.get('estrutura_prova', {})
                nova_estrutura = {}
                for disciplina in disciplinas:
                    st.markdown(f"**{disciplina}**")
                    col1, col2 = st.columns(2)
                    dados_atuais = estrutura_atual.get(disciplina, {'num_questoes': 0, 'peso': 1.0})
                    num_questoes = col1.number_input(f"Nº de Questões", value=dados_atuais.get('num_questoes', 0), key=f"q_edit_{disciplina}", min_value=0, step=1)
                    peso = col2.number_input(f"Peso", value=dados_atuais.get('peso', 1.0), key=f"p_edit_{disciplina}", format="%.2f", min_value=0.0, step=0.1)
                    nova_estrutura[disciplina] = {'num_questoes': num_questoes, 'peso': peso}

                submitted = st.form_submit_button("Salvar Estrutura da Prova")
                if submitted:
                    with st.spinner("Salvando estrutura..."):
                        try:
                            db.collection('perfis_concursos').document(perfil['id_documento']).update({'estrutura_prova': nova_estrutura})
                            st.success("Estrutura da prova salva com sucesso!")
                            del st.session_state.perfil_para_editar_estrutura
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao salvar a estrutura: {e}")
        else:
            st.error("Não foi possível carregar as disciplinas para este perfil.")
            if st.button("Ok"):
                del st.session_state.perfil_para_editar_estrutura
                st.rerun()

# --- Aba de Criação de Perfil ---
with tab2:
    st.subheader("Criar Novo Perfil de Concurso")
    with st.form("novo_perfil_form", clear_on_submit=True):
        nome = st.text_input("Nome do Concurso (ex: Câmara de Caxias do Sul/RS)")
        cargo = st.text_input("Cargo (ex: Assessor Legislativo)")
        ano = st.number_input("Ano do Concurso (ex: 2025)", min_value=2000, max_value=2100, step=1, value=datetime.now().year)
        
        uploaded_file = st.file_uploader("Carregue o arquivo CSV do edital", type=["csv"])

        st.markdown("---")
        st.markdown("##### Estrutura da Prova")
        st.caption("Insira o nº de questões e o peso de cada disciplina na prova real.")
        
        estrutura_prova = {}
        if uploaded_file:
            try:
                uploaded_file.seek(0)
                df_temp = pd.read_csv(uploaded_file, sep=';', encoding='latin-1')
                
                # "VACINA": Limpa os nomes das colunas para evitar problemas futuros
                df_temp.columns = df_temp.columns.str.strip()

                if 'Disciplina' in df_temp.columns:
                    disciplinas_unicas = df_temp['Disciplina'].unique()
                    for disciplina in disciplinas_unicas:
                        st.markdown(f"**{disciplina}**")
                        col1, col2 = st.columns(2)
                        num_questoes = col1.number_input(f"Nº de Questões", key=f"q_{disciplina}", min_value=0, step=1)
                        peso = col2.number_input(f"Peso", key=f"p_{disciplina}", min_value=0.0, step=0.1, format="%.1f", value=1.0)
                        estrutura_prova[disciplina] = {'num_questoes': num_questoes, 'peso': peso}
                else:
                    st.error("O arquivo CSV precisa ter uma coluna chamada 'Disciplina'.")
                uploaded_file.seek(0)
            except Exception as e:
                st.error(f"Erro ao processar o arquivo CSV: {e}")

        submitted = st.form_submit_button("Criar Perfil", type="primary")
        if submitted:
            if not all([nome, cargo, ano, uploaded_file]) or not estrutura_prova:
                st.warning("Por favor, preencha todos os campos, carregue um arquivo de edital e preencha a estrutura da prova.")
            else:
                with st.spinner("Criando novo perfil..."):
                    try:
                        id_perfil = f"{nome.lower().replace(' ', '_').replace('/', '')}_{cargo.lower().replace(' ', '_')}_{ano}"
                        
                        df_edital = pd.read_csv(uploaded_file, encoding='latin-1', sep=';')
                        # "VACINA" APLICADA AQUI TAMBÉM
                        df_edital.columns = df_edital.columns.str.strip()

                        df_edital['ID'] = df_edital.index + 1
                        df_edital['Teoria (T)'] = '[ ]'
                        df_edital['Domínio'] = '[Não Medido]'
                        df_edital['%'] = 0.0
                        df_edital['Total_Questoes_Topico'] = 0
                        df_edital['Total_Acertos_Topico'] = 0
                        df_edital['Ultima_Medicao'] = '-'
                        
                        colecao_dashboard = f"dashboard_{id_perfil}"
                        colecao_historico = f"historico_{id_perfil}"
                        
                        perfil_doc = {'nome': nome, 'cargo': cargo, 'ano': ano, 'status': 'Ativo',
                                      'nota_final': None, 'estrutura_prova': estrutura_prova,
                                      'colecao_dashboard': colecao_dashboard, 'colecao_historico': colecao_historico}
                        
                        db.collection('perfis_concursos').document(id_perfil).set(perfil_doc)

                        batch = db.batch()
                        for _, row in df_edital.iterrows():
                            doc_ref = db.collection(colecao_dashboard).document(str(row['ID']))
                            batch.set(doc_ref, row.to_dict())
                        batch.commit()
                        
                        st.success(f"Perfil '{nome}' criado com sucesso!")
                        st.balloons()
                        st.cache_data.clear()

                    except Exception as e:
                        st.error(f"Erro ao criar o perfil: {e}")

