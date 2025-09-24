# Importando as bibliotecas necessárias
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

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

# --- FUNÇÕES DE DADOS ---
def carregar_dashboard():
    """Carrega os dados do Firebase e retorna um DataFrame."""
    print("Carregando dashboard da nuvem (Firebase)...")
    try:
        docs = db.collection('dashboard').stream()
        lista_de_topicos = [doc.to_dict() for doc in docs]
        
        if not lista_de_topicos:
            return pd.DataFrame()

        df_bruto = pd.DataFrame(lista_de_topicos)
        colunas_finais = ['ID', 'Disciplina', 'Tópico do Edital', 'Teoria (T)', 'Qsts', 'Acertos', 'Domínio', '%', 'Últ. Medição']
        df_final = pd.DataFrame(columns=colunas_finais)

        df_final['ID'] = df_bruto.get('ID')
        df_final['Disciplina'] = df_bruto.get('Disciplina')
        df_final['Tópico do Edital'] = df_bruto.get('Tópico do Edital')
        df_final['Teoria (T)'] = df_bruto.get('Teoria (T)')
        df_final['Domínio'] = df_bruto.get('Domínio')
        df_final['%'] = df_bruto.get('%')
        df_final['Qsts'] = df_bruto.get('Total_Questoes_Topico', 0)
        df_final['Acertos'] = df_bruto.get('Total_Acertos_Topico', 0)
        df_final['Últ. Medição'] = df_bruto.get('Ultima_Medicao', '-')
    
        df_final.fillna({'Qsts': 0, 'Acertos': 0, '%': 0}, inplace=True)
        df_final.fillna('-', inplace=True)
        
        df_final['ID'] = pd.to_numeric(df_final['ID'])
        df_final['%'] = pd.to_numeric(df_final['%'])
        df_final['Qsts'] = pd.to_numeric(df_final['Qsts'])
        df_final['Acertos'] = pd.to_numeric(df_final['Acertos'])
        
        df_final = df_final.sort_values(by='ID').reset_index(drop=True)
        return df_final[colunas_finais]

    except Exception as e:
        print(f"Erro ao carregar dados do Firebase: {e}")
        return pd.DataFrame()

def get_nivel_dominio(percentual):
    """Retorna o nível de domínio com base no percentual de acerto."""
    if percentual >= 90: return '[Domínio Mestre]'
    elif 80 <= percentual < 90: return '[Domínio Sólido]'
    elif 65 <= percentual < 80: return '[Em Desenvolvimento]'
    else: return '[Revisão Urgente]'

# --- FUNÇÕES DE VISUALIZAÇÃO E ANÁLISE ---
def visualizar_dashboard(df):
    if df.empty: return
    print("\n--- SEU DASHBOARD DE PERFORMANCE ATUAL (SINCRONIZADO) ---")
    print(df.to_string())
    
    total_geral_questoes = df['Qsts'].sum()
    total_geral_acertos = df['Acertos'].sum()
    
    if total_geral_questoes > 0:
        percentual_geral = round((total_geral_acertos / total_geral_questoes) * 100, 2)
        print("\n--- RESUMO GERAL DE PERFORMANCE ---")
        print(f"Total de Questões Feitas: {int(total_geral_questoes)}")
        print(f"Total de Acertos: {int(total_geral_acertos)}")
        print(f"Percentual de Acerto Geral: {percentual_geral}%")
        print("-----------------------------------")
    print("---------------------------------------------------------\n")


def gerar_plano_acao(df):
    if df.empty: return
    print("\n--- PLANO DE AÇÃO E FOCO RECOMENDADO ---")
    revisao_urgente = df[df['Domínio'] == '[Revisão Urgente]']
    em_desenvolvimento = df[df['Domínio'] == '[Em Desenvolvimento]']
    nao_medido = df[df['Domínio'] == '[Não Medido]']
    print("\n[PRIORIDADE MÁXIMA] Tópicos para Reforço:")
    if not revisao_urgente.empty:
        print("Revisão Urgente (seu foco nº 1):")
        for _, row in revisao_urgente.iterrows(): print(f"  - ID {row['ID']}: {row['Tópico do Edital']} ({row['Disciplina']}) - Desempenho: {row['%']}%")
    if not em_desenvolvimento.empty:
        print("Em Desenvolvimento (seu foco nº 2):")
        for _, row in em_desenvolvimento.iterrows(): print(f"  - ID {row['ID']}: {row['Tópico do Edital']} ({row['Disciplina']}) - Desempenho: {row['%']}%")
    if revisao_urgente.empty and em_desenvolvimento.empty: print("Nenhum tópico precisando de reforço imediato. Ótimo trabalho!")
    print("\n[PRÓXIMOS PASSOS] Tópicos para Estudar e Medir:")
    if not nao_medido.empty:
        print("Sugestão de tópicos 'Não Medidos' para o próximo ciclo de estudo (T-Q-R):")
        prioridade_alta = nao_medido[nao_medido['Disciplina'].isin(['Língua Portuguesa', 'Legislação Municipal', 'Legislação Geral'])]
        sugestoes = prioridade_alta.head(3) if not prioridade_alta.empty else nao_medido.head(3)
        for _, row in sugestoes.iterrows(): print(f"  - ID {row['ID']}: {row['Tópico do Edital']} ({row['Disciplina']})")
    else: print("Parabéns! Todos os tópicos do edital já foram medidos ao menos uma vez!")
    print("-------------------------------------------\n")

def gerar_relatorio_disciplina(df):
    if df.empty: return
    print("\n--- RELATÓRIO DE PERFORMANCE POR DISCIPLINA ---")
    
    df_medidos = df[df['Qsts'] > 0].copy()
    if df_medidos.empty:
        print("Nenhum tópico foi medido ainda para gerar o relatório de disciplina.")
        return

    relatorio_agrupado = df.groupby('Disciplina').agg(
        Total_Questoes=('Qsts', 'sum'),
        Total_Acertos=('Acertos', 'sum'),
        Topicos_Total=('ID', 'count')
    ).reset_index()

    media_percentuais = df_medidos.groupby('Disciplina')['%'].mean().round(2).reset_index().rename(columns={'%': 'Média de Performance (%)'})
    relatorio_agrupado = pd.merge(relatorio_agrupado, media_percentuais, on='Disciplina', how='left')

    relatorio_agrupado['Performance Geral (%)'] = (relatorio_agrupado['Total_Acertos'] / relatorio_agrupado['Total_Questoes'] * 100).round(2)
    relatorio_agrupado.fillna(0, inplace=True)

    topicos_medidos_contagem = df_medidos.groupby('Disciplina')['ID'].count().reset_index().rename(columns={'ID': 'Tópicos Medidos'})
    relatorio_final = pd.merge(relatorio_agrupado, topicos_medidos_contagem, on='Disciplina', how='left')
    
    relatorio_final['Tópicos Medidos'] = relatorio_final['Tópicos Medidos'].fillna(0)
    
    relatorio_final['Tópicos Medidos'] = relatorio_final['Tópicos Medidos'].astype(int)
    relatorio_final['Progresso da Medição'] = (relatorio_final['Tópicos Medidos'] / relatorio_final['Topicos_Total'] * 100).round(2).astype(str) + '%'

    relatorio_final = relatorio_final.rename(columns={'Topicos_Total': 'Total Tópicos'})
    colunas_exibicao = ['Disciplina', 'Total Questões', 'Total Acertos', 'Performance Geral (%)', 'Média de Performance (%)', 'Tópicos Medidos', 'Total Tópicos', 'Progresso da Medição']
    
    relatorio_final = relatorio_final.rename(columns={'Total_Questoes': 'Total Questões', 'Total_Acertos': 'Total Acertos'})

    print(relatorio_final[colunas_exibicao].to_string(index=False))
    print("-------------------------------------------------\n")

# --- NOVA FUNÇÃO: RELATÓRIO DE ATIVIDADE DIÁRIA ---
def gerar_relatorio_atividade_diaria():
    """Busca o histórico e mostra um resumo de questões feitas por dia."""
    print("\n--- RELATÓRIO DE ATIVIDADE DIÁRIA ---")
    try:
        historico_docs = db.collection('historico').stream()
        lista_historico = [doc.to_dict() for doc in historico_docs]

        if not lista_historico:
            print("Nenhum registro no histórico para gerar o relatório.")
            return

        df_hist = pd.DataFrame(lista_historico)

        # Agrupa por data e calcula os totais
        atividade_diaria = df_hist.groupby('Data').agg(
            Total_Questoes=('Total_Questoes', 'sum'),
            Total_Acertos=('Acertos', 'sum')
        ).reset_index()

        # Calcula o percentual do dia
        atividade_diaria['%'] = (atividade_diaria['Total_Acertos'] / atividade_diaria['Total_Questoes'] * 100).round(2)

        # Ordena pela data, do mais recente para o mais antigo
        atividade_diaria['Data_Ordenada'] = pd.to_datetime(atividade_diaria['Data'], format='%d/%m/%Y')
        atividade_diaria = atividade_diaria.sort_values(by='Data_Ordenada', ascending=False)

        # Remove a coluna auxiliar e exibe
        print(atividade_diaria[['Data', 'Total_Questoes', 'Total_Acertos', '%']].to_string(index=False))
        print("-------------------------------------\n")

    except Exception as e:
        print(f"Ocorreu um erro ao gerar o relatório de atividade: {e}")


# --- FUNÇÕES DE REGISTRO ---
def registrar_estudo_teorico(df):
    try:
        id_topico = int(input("Digite o ID do tópico que concluiu a teoria (T): "))
        if id_topico in df['ID'].values:
            db.collection('dashboard').document(str(id_topico)).update({'Teoria (T)': '[X]'})
            print(f"Tópico {id_topico} atualizado na nuvem.")
    except Exception as e: print(f"Ocorreu um erro: {e}")

def lancar_simulado(df_dashboard):
    print("\n--- LANÇAMENTO DE RESULTADO DE SIMULADO (NA NUVEM) ---")
    try:
        ids_str = input("Digite os IDs dos tópicos avaliados, separados por vírgula (ex: 1,2,3): ")
        ids_avaliados = [int(i.strip()) for i in ids_str.split(',')]

        for id_topico in ids_avaliados:
            if id_topico in df_dashboard['ID'].values:
                total_questoes_sessao = int(input(f"Questões do tópico ID {id_topico}: "))
                acertos_sessao = int(input(f"Acertos para o tópico ID {id_topico}: "))
                
                if total_questoes_sessao > 0 and acertos_sessao <= total_questoes_sessao:
                    dados_antigos = df_dashboard.loc[df_dashboard['ID'] == id_topico]
                    total_questoes_antigo = dados_antigos['Qsts'].iloc[0]
                    total_acertos_antigo = dados_antigos['Acertos'].iloc[0]
                    
                    novo_total_questoes = total_questoes_antigo + total_questoes_sessao
                    novo_total_acertos = total_acertos_antigo + acertos_sessao
                    
                    percentual_geral = round((novo_total_acertos / novo_total_questoes) * 100, 2) if novo_total_questoes > 0 else 0
                    data_hoje = datetime.now().strftime('%d/%m/%Y')
                    
                    db.collection('historico').add({'ID_Topico': id_topico, 'Data': data_hoje, 'Total_Questoes': total_questoes_sessao, 'Acertos': acertos_sessao, '%': (acertos_sessao/total_questoes_sessao)*100})
                    
                    dados_para_atualizar = {
                        'Domínio': get_nivel_dominio(percentual_geral),
                        '%': percentual_geral,
                        'Ultima_Medicao': data_hoje,
                        'Total_Questoes_Topico': novo_total_questoes,
                        'Total_Acertos_Topico': novo_total_acertos
                    }
                    db.collection('dashboard').document(str(id_topico)).update(dados_para_atualizar)
                    print(f"-> Resultado do tópico {id_topico} registrado e totais atualizados!")
                else: print(f"Valores inválidos para o tópico {id_topico}.")
            else: print(f"ID {id_topico} não encontrado.")
        print("\nSimulado registrado e sincronizado!")
    except Exception as e: print(f"Ocorreu um erro: {e}")

def gerenciar_historico(df_dashboard):
    """Menu para gerenciar o histórico de lançamentos."""
    while True:
        print("\n--- Gerenciador de Histórico ---")
        print("[1] Visualizar lançamentos de um tópico")
        print("[2] Apagar um lançamento específico")
        print("[3] Voltar ao menu principal")
        escolha = input("Escolha uma opção: ")

        if escolha == '1':
            try:
                id_topico = int(input("Digite o ID do tópico para ver o histórico: "))
                historico_ref = db.collection('historico').where('ID_Topico', '==', id_topico).order_by('Data').stream()
                registros = list(historico_ref)
                if not registros:
                    print(f"Nenhum registro encontrado para o tópico ID {id_topico}.")
                    continue
                print(f"\n--- Histórico de Lançamentos para o Tópico ID {id_topico} ---")
                for doc in registros:
                    dados = doc.to_dict()
                    print(f"  - ID do Registro: {doc.id}")
                    print(f"    Data: {dados.get('Data', 'N/A')}, Questões: {dados.get('Total_Questoes', 'N/A')}, Acertos: {dados.get('Acertos', 'N/A')}, %: {dados.get('%', 'N/A')}")
                print("-------------------------------------------------")
            except Exception as e: print(f"Ocorreu um erro: {e}")
        elif escolha == '2':
            try:
                doc_id_para_apagar = input("Digite o ID do Registro que deseja apagar: ").strip()
                if not doc_id_para_apagar:
                    print("ID do Registro não pode ser vazio.")
                    continue
                doc_ref = db.collection('historico').document(doc_id_para_apagar)
                doc = doc_ref.get()
                if not doc.exists:
                    print(f"Erro: Registro com ID '{doc_id_para_apagar}' não encontrado.")
                    continue
                dados_apagados = doc.to_dict()
                doc_ref.delete()
                print(f"Registro '{doc_id_para_apagar}' apagado do histórico com sucesso.")
                
                id_topico = dados_apagados['ID_Topico']
                questoes_apagadas = dados_apagados['Total_Questoes']
                acertos_apagados = dados_apagados['Acertos']
                
                print("Reajustando totais no dashboard...")
                dados_dashboard = df_dashboard.loc[df_dashboard['ID'] == id_topico]
                total_questoes_antigo = dados_dashboard['Qsts'].iloc[0]
                total_acertos_antigo = dados_dashboard['Acertos'].iloc[0]

                novo_total_questoes = total_questoes_antigo - questoes_apagadas
                novo_total_acertos = total_acertos_antigo - acertos_apagados
                percentual_geral = round((novo_total_acertos / novo_total_questoes) * 100, 2) if novo_total_questoes > 0 else 0
                
                db.collection('dashboard').document(str(id_topico)).update({
                    'Total_Questoes_Topico': novo_total_questoes,
                    'Total_Acertos_Topico': novo_total_acertos,
                    '%': percentual_geral,
                    'Domínio': get_nivel_dominio(percentual_geral)
                })
                print(f"Dashboard para o tópico ID {id_topico} atualizado.")
            except Exception as e: print(f"Ocorreu um erro: {e}")
        elif escolha == '3':
            break
        else:
            print("Opção inválida.")

# --- FUNÇÃO PRINCIPAL ---
def main():
    if not db: return
    while True:
        df_dashboard = carregar_dashboard()
        print("\n=== Coach de Concursos (Terminal / Nuvem) ===")
        print("[1] Visualizar Dashboard Completo\n[2] Registrar Estudo Teórico (T)\n[3] Lançar Resultado de Simulado\n[4] Gerar Plano de Ação\n[5] Relatório por Disciplina\n[6] Gerenciar Histórico\n[7] Relatório de Atividade Diária\n[8] Sair")
        escolha = input("Escolha uma opção: ")
        if escolha == '1': visualizar_dashboard(df_dashboard)
        elif escolha == '2': registrar_estudo_teorico(df_dashboard)
        elif escolha == '3': lancar_simulado(df_dashboard)
        elif escolha == '4': gerar_plano_acao(df_dashboard)
        elif escolha == '5': gerar_relatorio_disciplina(df_dashboard)
        elif escolha == '6': gerenciar_historico(df_dashboard)
        elif escolha == '7': gerar_relatorio_atividade_diaria() # NOVA OPÇÃO
        elif escolha == '8':
            print("Bons estudos! Seus dados estão salvos e sincronizados na nuvem.")
            break
        else: print("Opção inválida.")

if __name__ == "__main__":
    main()