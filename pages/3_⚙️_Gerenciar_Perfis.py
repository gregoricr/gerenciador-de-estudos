import streamlit as st
import pandas as pd
from firebase_admin import firestore
import os
from datetime import datetime, timedelta

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
        perfis_ordenados = dict(sorted(perfis.items(), key=lambda item: (item[1].get('status', 'Ativo'), item[1]['nome'])))
        return perfis_ordenados
    except Exception as e:
        st.error(f"Erro ao carregar perfis: {e}")
        return {}

def ler_csv_flexivel(uploaded_file):
    """Lê o CSV detectando o separador e limpando colunas."""
    try:
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file, sep=';', encoding='latin-1')
        if len(df.columns) <= 1:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, sep=',', encoding='latin-1')
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except Exception as e:
        st.error(f"Erro ao processar o arquivo CSV: {e}")
        return None

def excluir_colecao_completa(nome_colecao):
    """Função utilitária para apagar todos os documentos de uma coleção (batch)."""
    if not nome_colecao:
        return
    docs = db.collection(nome_colecao).limit(500).stream()
    deleted = 0
    batch = db.batch()
    for doc in docs:
        batch.delete(doc.reference)
        deleted += 1
    if deleted > 0:
        batch.commit()
        # Recursivo caso haja mais de 500 documentos
        if deleted == 500:
            excluir_colecao_completa(nome_colecao)

@st.cache_data(ttl=300)
def get_disciplinas_from_dashboard(_perfil):
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
st.set_page_config(page_title="Gerenciar Perfis", page_icon="⚙️", layout="centered")

st.markdown("# ⚙️ Gerenciar Perfis")
tab1, tab2 = st.tabs(["Gerenciar Existentes", "Criar Novo Perfil"])

# --- ABA 1: GESTÃO DE STATUS, ESTRUTURA E EXCLUSÃO ---
with tab1:
    st.subheader("Concursos Registrados")
    perfis = carregar_todos_perfis()

    if not perfis:
        st.info("Nenhum perfil encontrado.")
    else:
        for perfil_id, perfil in perfis.items():
            with st.container(border=True):
                col_info, col_action = st.columns([1.5, 1.5])
                with col_info:
                    st.markdown(f"**{perfil['nome']}** ({perfil['ano']})")
                    status = perfil.get('status', 'Ativo')
                    st.caption(f"Status: **{status}**")

                with col_action:
                    if status == 'Ativo':
                        c1, c2, c3 = st.columns(3)
                        if c1.button("Meta", key=f"m_{perfil_id}", use_container_width=True):
                            st.session_state.perfil_para_definir_meta = perfil
                            st.rerun()
                        if c2.button("Arq", key=f"a_{perfil_id}", use_container_width=True):
                            st.session_state.perfil_para_arquivar = perfil
                            st.rerun()
                        if c3.button("🗑️", key=f"del_{perfil_id}", use_container_width=True, help="Excluir Perfil"):
                            st.session_state.perfil_para_excluir = perfil
                            st.rerun()
                    else:
                        c1, c2, c3, c4 = st.columns(4)
                        if c1.button("✅", key=f"r_{perfil_id}", use_container_width=True, help="Reativar"):
                            db.collection('perfis_concursos').document(perfil_id).update({'status': 'Ativo'})
                            st.cache_data.clear()
                            st.rerun()
                        if c2.button("📝", key=f"n_{perfil_id}", use_container_width=True, help="Nota"):
                            st.session_state.perfil_para_editar_nota = perfil
                            st.rerun()
                        if c3.button("📖", key=f"e_{perfil_id}", use_container_width=True, help="Edital"):
                            st.session_state.perfil_para_editar_estrutura = perfil
                            st.rerun()
                        if c4.button("🗑️", key=f"del_{perfil_id}", use_container_width=True, help="Excluir Perfil"):
                            st.session_state.perfil_para_excluir = perfil
                            st.rerun()

    st.markdown("---")
    
    # --- FORMULÁRIOS DE AÇÃO ---

    # FORMULÁRIO DE EXCLUSÃO (NOVO)
    if 'perfil_para_excluir' in st.session_state:
        p = st.session_state.perfil_para_excluir
        with st.container(border=True):
            st.error(f"⚠️ **ATENÇÃO:** Você está prestes a excluir permanentemente o perfil: **{p['nome']}**")
            st.write("Esta ação apagará todo o dashboard de tópicos, histórico de simulados e registros de tempo. Não há como desfazer.")
            
            c_canc, c_conf = st.columns(2)
            if c_canc.button("Cancelar", use_container_width=True):
                del st.session_state.perfil_para_excluir
                st.rerun()
            
            if c_conf.button("Sim, Excluir Tudo", type="primary", use_container_width=True):
                with st.spinner("Limpando todos os registros do banco de dados..."):
                    try:
                        # 1. Apaga coleções vinculadas
                        excluir_colecao_completa(p.get('colecao_dashboard'))
                        excluir_colecao_completa(p.get('colecao_historico'))
                        excluir_colecao_completa(f"historico_tempo_{p['id_documento']}")
                        
                        # 2. Apaga o documento principal do perfil
                        db.collection('perfis_concursos').document(p['id_documento']).delete()
                        
                        st.success(f"O perfil '{p['nome']}' foi removido com sucesso.")
                        if 'perfil_selecionado' in st.session_state and st.session_state.perfil_selecionado['id_documento'] == p['id_documento']:
                            del st.session_state.perfil_selecionado
                        
                        del st.session_state.perfil_para_excluir
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao excluir: {e}")

    # (Lógica de Metas, Arquivamento e Notas permanecem aqui...)
    if 'perfil_para_definir_meta' in st.session_state:
        p = st.session_state.perfil_para_definir_meta
        with st.form("form_meta"):
            st.info(f"Metas para: {p['nome']}")
            q = st.number_input("Questões/Semana", value=300)
            h = st.number_input("Horas/Semana", value=20)
            if st.form_submit_button("Salvar"):
                hoje = datetime.now()
                ini = hoje - timedelta(days=hoje.weekday())
                fim = ini + timedelta(days=6)
                db.collection('perfis_concursos').document(p['id_documento']).update({
                    'meta_semanal': {"questoes_objetivo": q, "horas_objetivo": h, 
                                     "data_inicio": ini.strftime('%d/%m/%Y'), "data_fim": fim.strftime('%d/%m/%Y')}
                })
                st.success("Meta salva!")
                del st.session_state.perfil_para_definir_meta
                st.cache_data.clear()
                st.rerun()

# --- ABA 2: CRIAR NOVO PERFIL ---
with tab2:
    st.subheader("Cadastrar Novo Concurso")
    nome = st.text_input("Nome do Concurso (ex: SEFAZ/RS)")
    cargo = st.text_input("Cargo")
    ano = st.number_input("Ano", min_value=2020, value=datetime.now().year)
    file = st.file_uploader("Upload do Edital (CSV)", type=["csv"])
    
    if file:
        df_csv = ler_csv_flexivel(file)
        if df_csv is not None:
            st.success(f"Arquivo carregado: {len(df_csv)} linhas encontradas.")
            st.markdown("---")
            st.subheader("🛠️ Mapeamento de Colunas")
            c_m, c_t = st.columns(2)
            
            def sugerir_coluna(lista, termos):
                for i, col in enumerate(lista):
                    if any(t in col.lower() for t in termos): return i
                return 0

            coluna_materia = c_m.selectbox("Qual coluna contém as MATÉRIAS?", 
                                           options=df_csv.columns, 
                                           index=sugerir_coluna(df_csv.columns, ['disciplina', 'matéria', 'materia', 'área']))
            coluna_topico = c_t.selectbox("Qual coluna contém os TÓPICOS?", 
                                          options=df_csv.columns, 
                                          index=sugerir_coluna(df_csv.columns, ['tópico', 'conteúdo', 'assunto', 'item']))

            materias_unicas = sorted(df_csv[coluna_materia].dropna().unique().tolist())
            st.markdown("---")
            st.subheader("📝 Estrutura da Prova")
            with st.form("form_final_criacao"):
                estrutura_final = {}
                for m in materias_unicas:
                    st.markdown(f"**{m}**")
                    col_q, col_p = st.columns(2)
                    nq = col_q.number_input(f"Questões", key=f"nq_new_{m}", min_value=0, step=1)
                    ps = col_p.number_input(f"Peso", key=f"ps_new_{m}", min_value=0.1, value=1.0, format="%.1f")
                    estrutura_final[m] = {'num_questoes': nq, 'peso': ps}

                if st.form_submit_button("CRIAR PERFIL COMPLETO", type="primary", use_container_width=True):
                    if not nome or not cargo or not estrutura_final:
                        st.error("Por favor, preencha o nome, cargo e a estrutura da prova.")
                    else:
                        with st.spinner("Criando perfil e importando edital..."):
                            try:
                                df_sistema = df_csv[[coluna_materia, coluna_topico]].copy()
                                df_sistema.columns = ['Disciplina', 'Tópico do Edital']
                                df_sistema['ID'] = range(1, len(df_sistema) + 1)
                                df_sistema['Teoria (T)'] = '[ ]'
                                df_sistema['Domínio'] = '[Não Medido]'
                                df_sistema['%'] = 0.0
                                df_sistema['Total_Questoes_Topico'] = 0
                                df_sistema['Total_Acertos_Topico'] = 0
                                df_sistema['Ultima_Medicao'] = '-'
                                
                                id_p = f"{nome.lower().replace(' ', '_').replace('/', '')}_{ano}"
                                col_dash = f"dashboard_{id_p}"
                                col_hist = f"historico_{id_p}"
                                
                                db.collection('perfis_concursos').document(id_p).set({
                                    'nome': nome, 'cargo': cargo, 'ano': ano, 'status': 'Ativo',
                                    'estrutura_prova': estrutura_final,
                                    'colecao_dashboard': col_dash, 'colecao_historico': col_hist
                                })

                                batch = db.batch()
                                for _, row in df_sistema.iterrows():
                                    d_ref = db.collection(col_dash).document(str(row['ID']))
                                    batch.set(d_ref, row.to_dict())
                                batch.commit()
                                
                                st.success("Perfil criado com sucesso!")
                                st.balloons()
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao salvar: {e}")