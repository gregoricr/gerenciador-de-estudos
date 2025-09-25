# Importando as bibliotecas necessárias
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import sys
import os

# --- CONFIGURAÇÕES DE EXIBIÇÃO DO PANDAS ---
pd.set_option('display.width', 1000)
pd.set_option('display.max_columns', 12)
pd.set_option('display.max_colwidth', 50)

# --- NOME DO ARQUIVO DE CREDENCIAIS ---
NOME_ARQUIVO_CREDENCIAL = 'firebase_credentials.json'

# --- INICIALIZAÇÃO DO FIREBASE ---
def inicializar_firebase():
    """Inicializa a conexão com o Firebase."""
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(NOME_ARQUIVO_CREDENCIAL)
            firebase_admin.initialize_app(cred)
        return firestore.client()
    except Exception as e:
        print(f"ERRO CRÍTICO: Não foi possível conectar ao Firebase. Verifique o arquivo '{NOME_ARQUIVO_CREDENCIAL}'.")
        print(f"Detalhe do erro: {e}")
        return None

db = inicializar_firebase()

# --- FUNÇÕES DE DADOS (SENSÍVEIS AO PERFIL) ---
def carregar_dashboard(perfil):
    """Carrega os dados do Firebase para um perfil específico e retorna um DataFrame."""
    colecao_dashboard = perfil['colecao_dashboard']
    print(f"\nCarregando dashboard da nuvem (Perfil: {perfil['nome']})...")
    try:
        docs = db.collection(colecao_dashboard).stream()
        lista_de_topicos = [doc.to_dict() for doc in docs]
        
        if not lista_de_topicos:
            return pd.DataFrame()

        df_bruto = pd.DataFrame(lista_de_topicos)
        colunas_finais = ['ID', 'Disciplina', 'Tópico do Edital', 'Teoria (T)', 'Qsts', 'Acertos', 'Domínio', '%', 'Últ. Medição']
        df_final = pd.DataFrame()

        df_bruto.rename(columns={'Total_Questoes_Topico': 'Qsts', 
                                 'Total_Acertos_Topico': 'Acertos', 
                                 'Ultima_Medicao': 'Últ. Medição'}, inplace=True, errors='ignore')

        for col in colunas_finais:
            if col in df_bruto.columns:
                df_final[col] = df_bruto[col]
            else:
                df_final[col] = 0 if col in ['Qsts', 'Acertos', '%'] else '-'
        
        df_final.fillna({'Qsts': 0, 'Acertos': 0, '%': 0}, inplace=True)
        df_final.fillna('-', inplace=True)
        
        for col in ['ID', '%', 'Qsts', 'Acertos']:
             df_final[col] = pd.to_numeric(df_final[col], errors='coerce').fillna(0)

        df_final['ID'] = df_final['ID'].astype(int)
        df_final = df_final.sort_values(by='ID').reset_index(drop=True)
        return df_final[colunas_finais]

    except Exception as e:
        print(f"Erro ao carregar dados do Firebase: {e}")
        return pd.DataFrame()

# --- FUNÇÕES DE VISUALIZAÇÃO ---
def visualizar_dashboard(df_dashboard):
    if df_dashboard.empty: 
        print("Dashboard vazio ou não encontrado para este perfil.")
        return
    print(f"\n--- DASHBOARD DE PERFORMANCE (SINCRONIZADO) ---")
    print(df_dashboard.to_string())
    
    total_geral_questoes = df_dashboard['Qsts'].sum()
    total_geral_acertos = df_dashboard['Acertos'].sum()
    
    if total_geral_questoes > 0:
        percentual_geral = round((total_geral_acertos / total_geral_questoes) * 100, 2)
        print("\n--- RESUMO GERAL DE PERFORMANCE (PERFIL ATUAL) ---")
        print(f"Total de Questões Feitas: {int(total_geral_questoes)}")
        print(f"Total de Acertos: {int(total_geral_acertos)}")
        print(f"Percentual de Acerto Geral: {percentual_geral}%")
    print("-------------------------------------------------\n")

def get_nivel_dominio(percentual):
    if percentual >= 90: return '[Domínio Mestre]'
    elif 80 <= percentual < 90: return '[Domínio Sólido]'
    elif 65 <= percentual < 80: return '[Em Desenvolvimento]'
    else: return '[Revisão Urgente]'

# --- FUNÇÕES DO PERFIL ATIVO ---

@firestore.transactional
def transacao_lancar_simulado(transaction, doc_ref, novas_questoes, novos_acertos):
    """Executa a atualização de um tópico do simulado dentro de uma transação."""
    snapshot = doc_ref.get(transaction=transaction)
    
    total_questoes_antigo = snapshot.get('Total_Questoes_Topico') or 0
    total_acertos_antigo = snapshot.get('Total_Acertos_Topico') or 0

    novo_total_questoes = total_questoes_antigo + novas_questoes
    novo_total_acertos = total_acertos_antigo + novos_acertos
    
    percentual_geral = round((novo_total_acertos / novo_total_acertos) * 100, 2) if novo_total_acertos > 0 else 0
    
    dados_para_atualizar = {
        'Total_Questoes_Topico': novo_total_questoes,
        'Total_Acertos_Topico': novo_total_acertos,
        '%': percentual_geral,
        'Domínio': get_nivel_dominio(percentual_geral),
        'Ultima_Medicao': datetime.now().strftime('%d/%m/%Y')
    }
    transaction.update(doc_ref, dados_para_atualizar)

def lancar_simulado(perfil):
    """Registra o resultado de um simulado para o perfil ativo."""
    print("\n--- LANÇAMENTO DE RESULTADO DE SIMULADO ---")
    try:
        ids_str = input("Digite os IDs dos tópicos, separados por vírgula (ex: 1,2,3): ")
        ids_avaliados = [int(i.strip()) for i in ids_str.split(',')]
        
        colecao_dashboard = perfil['colecao_dashboard']
        colecao_historico = perfil['colecao_historico']

        for id_topico in ids_avaliados:
            total_questoes = int(input(f"Quantas questões do tópico ID {id_topico}? "))
            acertos = int(input(f"Quantas você acertou para o tópico ID {id_topico}? "))
            
            if total_questoes > 0:
                doc_ref = db.collection(colecao_dashboard).document(str(id_topico))
                transaction = db.transaction()
                transacao_lancar_simulado(transaction, doc_ref, total_questoes, acertos)

                db.collection(colecao_historico).add({
                    'ID_Topico': id_topico,
                    'Data': datetime.now().strftime('%d/%m/%Y'),
                    'Total_Questoes': total_questoes,
                    'Acertos': acertos,
                    '%': round((acertos / total_questoes) * 100, 2)
                })
                print(f"-> Tópico {id_topico} atualizado com sucesso!")
            else:
                print(f"Número de questões para o tópico {id_topico} deve ser maior que zero.")
        print("\nSimulado registrado e sincronizado!")
    except ValueError:
        print("Entrada inválida. Certifique-se de digitar os números corretamente.")
    except Exception as e:
        print(f"Ocorreu um erro: {e}")

# --- FUNÇÃO DE CRIAÇÃO DE PERFIL ---
def criar_novo_perfil():
    """Guia o usuário para criar um novo perfil de concurso."""
    print("\n--- CRIAÇÃO DE NOVO PERFIL DE CONCURSO ---")
    
    nome = input("Nome do Concurso (ex: Câmara de Caxias do Sul/RS): ")
    cargo = input("Cargo (ex: Assessor Legislativo): ")
    
    while True:
        try:
            ano_str = input("Ano do Concurso (ex: 2025): ")
            ano = int(ano_str)
            break
        except ValueError:
            print("ERRO: O ano deve ser um número inteiro. Tente novamente.")

    id_perfil = f"{nome.lower().replace(' ', '_').replace('/', '')}_{cargo.lower().replace(' ', '_')}_{ano}"
    
    print("\nAgora, vamos importar o conteúdo programático.")
    print("Você precisará de um arquivo CSV com duas colunas, com os cabeçalhos exatos: Disciplina,Tópico do Edital")
    caminho_csv = input("Insira o caminho completo para o arquivo CSV do edital: ")
    
    try:
        if not os.path.exists(caminho_csv):
            raise FileNotFoundError("Arquivo CSV não encontrado no caminho especificado.")

        df_edital = pd.read_csv(caminho_csv, encoding='latin-1', sep=';')
        
        if not all(col in df_edital.columns for col in ['Disciplina', 'Tópico do Edital']):
            raise ValueError("O arquivo CSV deve conter as colunas 'Disciplina' e 'Tópico do Edital'.")

        # CADASTRO DA ESTRUTURA DA PROVA
        print("\n--- CADASTRO DA ESTRUTURA DA PROVA ---")
        print("Agora, informe o número de questões e o peso para cada disciplina na prova real.")
        estrutura_prova = {}
        disciplinas_unicas = df_edital['Disciplina'].unique()
        for disciplina in disciplinas_unicas:
            while True:
                try:
                    num_questoes = int(input(f" - Nº de questões para '{disciplina}': "))
                    peso = float(input(f" - Peso para '{disciplina}' (ex: 1.5): ").replace(',', '.'))
                    estrutura_prova[disciplina] = {'num_questoes': num_questoes, 'peso': peso}
                    break
                except ValueError:
                    print("ERRO: O número de questões e o peso devem ser números. Tente novamente.")

        # Cria a estrutura do dashboard
        df_edital['ID'] = df_edital.index + 1
        df_edital['Teoria (T)'] = '[ ]'
        df_edital['Domínio'] = '[Não Medido]'
        df_edital['%'] = 0.0
        df_edital['Total_Questoes_Topico'] = 0
        df_edital['Total_Acertos_Topico'] = 0
        df_edital['Ultima_Medicao'] = '-'
        
        colecao_dashboard = f"dashboard_{id_perfil}"
        colecao_historico = f"historico_{id_perfil}"
        
        perfil_doc = {
            'nome': nome, 'cargo': cargo, 'ano': ano, 'status': 'Ativo',
            'nota_final': None, 'estrutura_prova': estrutura_prova,
            'colecao_dashboard': colecao_dashboard,
            'colecao_historico': colecao_historico
        }
        db.collection('perfis_concursos').document(id_perfil).set(perfil_doc)

        batch = db.batch()
        for _, row in df_edital.iterrows():
            doc_ref = db.collection(colecao_dashboard).document(str(row['ID']))
            batch.set(doc_ref, row.to_dict())
        batch.commit()
        
        print(f"\nPerfil '{nome} - {cargo}' criado com sucesso!")
        print(f"{len(df_edital)} tópicos foram importados para o seu novo dashboard.")

    except Exception as e:
        print(f"\n--- OCORREU UM ERRO INESPERADO ---")
        print(f"Não foi possível criar o perfil. Detalhe do erro:")
        print(e)
        print("------------------------------------")


def menu_perfil_ativo(perfil):
    """Mostra o menu de funcionalidades para um perfil ativo."""
    while True:
        print(f"\n=== Perfil Ativo: {perfil['nome']} - {perfil['cargo']} ({perfil['ano']}) ===")
        print("[1] Visualizar Dashboard Completo")
        print("[2] Lançar Resultado de Simulado")
        print("[3] Voltar para a seleção de perfis")
        
        escolha = input("Escolha uma opção: ")

        if escolha == '1':
            df_dashboard_atualizado = carregar_dashboard(perfil)
            visualizar_dashboard(df_dashboard_atualizado)
        elif escolha == '2':
            lancar_simulado(perfil)
        elif escolha == '3':
            break
        else:
            print("Opção inválida.")

# --- GERENCIADOR DE PERFIS ---
def gerar_relatorio_final(perfil, df_dashboard):
    """Gera a análise final comparando o desempenho nos estudos com a nota real da prova."""
    print(f"\n--- ANÁLISE DE PERFORMANCE FINAL: {perfil['nome']} ---")
    
    estrutura_prova = perfil.get('estrutura_prova', {})
    nota_real = perfil.get('nota_final')

    if not estrutura_prova:
        print("ERRO: A estrutura da prova (questões e pesos) não foi cadastrada para este perfil.")
        return
    if nota_real is None:
        print("ERRO: A nota final da prova não foi registrada para este perfil.")
        return

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
            'Pontuação Estimada': f"{pontuacao_estimada:.2f} de {pontuacao_maxima_disciplina:.2f}"
        })

    df_relatorio = pd.DataFrame(resultados)
    
    print(df_relatorio.to_string(index=False))
    print("---------------------------------------------------------------")
    print(f"NOTA SIMULADA FINAL (com base nos estudos): {nota_simulada_total:.2f}")
    print(f"NOTA REAL NA PROVA: {nota_real:.2f}")
    print("---------------------------------------------------------------")


def gerenciar_perfis():
    """Permite visualizar e gerenciar todos os perfis de concurso."""
    while True:
        print("\n--- GERENCIADOR DE PERFIS (ARQUIVO) ---")
        perfis_ref = db.collection('perfis_concursos').stream()
        todos_perfis_docs = list(perfis_ref)
        
        todos_perfis = {}
        for i, doc in enumerate(todos_perfis_docs):
            perfil_data = doc.to_dict()
            perfil_data['id_documento'] = doc.id
            todos_perfis[str(i+1)] = perfil_data

        if not todos_perfis:
            print("Nenhum perfil encontrado.")
            input("\nPressione Enter para voltar...")
            return

        print("Selecione um perfil para gerenciar:")
        for key, perfil in todos_perfis.items():
            nota_info = f" (Nota: {perfil.get('nota_final')})" if perfil.get('nota_final') is not None else ""
            print(f"[{key}] {perfil['nome']} ({perfil['ano']}) - Status: {perfil['status']}{nota_info}")

        print("-----------------------------------------")
        print("[V] Voltar ao menu principal")
        
        escolha = input("Escolha uma opção: ").upper()

        if escolha == 'V':
            break
        elif escolha in todos_perfis:
            perfil_selecionado = todos_perfis[escolha]
            
            # OPÇÕES PARA PERFIS ARQUIVADOS
            if perfil_selecionado['status'] == 'Arquivado':
                print(f"\nOpções para '{perfil_selecionado['nome']}':")
                print("[1] Reativar Perfil")
                if perfil_selecionado.get('nota_final') is not None:
                    print("[2] Ver Relatório Final de Performance")
                
                sub_escolha = input("Escolha uma opção: ")
                if sub_escolha == '1':
                    # Lógica para REATIVAR
                    try:
                        doc_ref = db.collection('perfis_concursos').document(perfil_selecionado['id_documento'])
                        doc_ref.update({'status': 'Ativo'})
                        print("\nPerfil reativado com sucesso!")
                    except Exception as e:
                        print(f"Erro ao reativar o perfil: {e}")
                elif sub_escolha == '2' and perfil_selecionado.get('nota_final') is not None:
                    # Lógica para mostrar RELATÓRIO FINAL
                    df_dashboard = carregar_dashboard(perfil_selecionado)
                    if not df_dashboard.empty:
                        gerar_relatorio_final(perfil_selecionado, df_dashboard)
                        input("\nPressione Enter para continuar...")
                    else:
                        print("Não foi possível carregar o dashboard para gerar o relatório.")

            # OPÇÕES PARA PERFIS ATIVOS
            else: 
                confirm_archive = input(f"\nDeseja ARQUIVAR o perfil '{perfil_selecionado['nome']}'? (S/N): ").upper()
                if confirm_archive == 'S':
                    nota_final = None
                    confirm_nota = input("Deseja registrar a nota final da prova? (S/N): ").upper()
                    if confirm_nota == 'S':
                        while True:
                            try:
                                nota_str = input("Digite a nota final (ex: 85.75): ")
                                nota_final = float(nota_str.replace(',', '.'))
                                break
                            except ValueError:
                                print("ERRO: A nota deve ser um número. Tente novamente.")
                    
                    try:
                        doc_ref = db.collection('perfis_concursos').document(perfil_selecionado['id_documento'])
                        doc_ref.update({'status': 'Arquivado', 'nota_final': nota_final})
                        print("\nPerfil arquivado com sucesso!")
                    except Exception as e:
                        print(f"Erro ao arquivar o perfil: {e}")
        else:
            print("Opção inválida.")


# --- NOVO MENU PRINCIPAL ---
def main():
    if not db: return

    while True:
        print("\n=== GERENCIADOR DE PERFIS DE CONCURSO ===")
        
        perfis_ref = db.collection('perfis_concursos').where(field_path='status', op_string='==', value='Ativo').stream()
        perfis_ativos_docs = list(perfis_ref)
        
        perfis_ativos = {}
        for i, doc in enumerate(perfis_ativos_docs):
            perfil_data = doc.to_dict()
            perfil_data['id_documento'] = doc.id
            perfis_ativos[str(i+1)] = perfil_data

        if perfis_ativos:
            print("Selecione um perfil de estudo ativo:")
            for key, perfil in perfis_ativos.items():
                print(f"[{key}] {perfil['nome']} - {perfil['cargo']} ({perfil['ano']})")
        else:
            print("Nenhum perfil ativo encontrado.")

        print("-----------------------------------------")
        print("[N] Criar Novo Perfil de Concurso")
        print("[A] Acessar e Gerenciar Arquivo de Concursos")
        print("[S] Sair")
        
        escolha_main = input("Escolha uma opção: ").upper()

        if escolha_main in perfis_ativos:
            perfil_selecionado = perfis_ativos[escolha_main]
            menu_perfil_ativo(perfil_selecionado)
        elif escolha_main == 'N':
            criar_novo_perfil()
        elif escolha_main == 'A':
            gerenciar_perfis()
        elif escolha_main == 'S':
            print("Bons estudos! Seus dados estão salvos e sincronizados na nuvem.")
            break
        else:
            print("Opção inválida. Tente novamente.")

if __name__ == "__main__":
    main()