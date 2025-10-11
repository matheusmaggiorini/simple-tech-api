# test_all_outflow_files.py
# Teste abrangente com todas as planilhas de saída

import pandas as pd
import sys
import os
import glob

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from core.business_event_analyzer import identify_key_business_events
from core.data_processing import processar_dados

def test_all_outflow_files():
    """Testa todas as planilhas de saída na pasta dados_de_saida."""
    print("="*80)
    print("TESTE ABRANGENTE COM TODAS AS PLANILHAS DE SAÍDA")
    print("="*80)
    
    # Lista todos os arquivos de saída
    outflow_files = glob.glob('data/dados_de_saida/*.xlsx')
    print(f"Encontrados {len(outflow_files)} arquivos de saída:")
    for file in outflow_files:
        print(f"  - {os.path.basename(file)}")
    print()
    
    # Carrega planilha de entrada
    try:
        df_entrada = pd.read_excel('data/Planilha_Entradas.xls')
        print(f"Planilha de entrada carregada: {len(df_entrada)} linhas")
    except Exception as e:
        print(f"❌ Erro ao carregar planilha de entrada: {e}")
        return None
    
    # Processa cada arquivo de saída individualmente
    all_outflow_data = []
    
    for outflow_file in outflow_files:
        try:
            print(f"\nProcessando: {os.path.basename(outflow_file)}")
            
            # Carrega o arquivo
            df_saida = pd.read_excel(outflow_file)
            print(f"  Linhas carregadas: {len(df_saida)}")
            
            # Processa o arquivo
            df_processed = processar_dados(df_saida, os.path.basename(outflow_file))
            print(f"  Linhas processadas: {len(df_processed)}")
            
            if not df_processed.empty:
                # Mostra algumas informações sobre os dados processados
                print(f"  Colunas: {list(df_processed.columns)}")
                if 'saida' in df_processed.columns:
                    total_saida = df_processed['saida'].sum()
                    print(f"  Total de saídas: R$ {total_saida:.2f}")
                
                # Verifica se há fornecedores identificados
                if 'descricao' in df_processed.columns:
                    fornecedores = df_processed['descricao'].unique()
                    fornecedores = [f for f in fornecedores if pd.notna(f) and f != '' and f != 'nan']
                    print(f"  Fornecedores encontrados: {fornecedores[:5]}")  # Mostra os primeiros 5
                
                all_outflow_data.append(df_processed)
            else:
                print("  ⚠️ Arquivo vazio após processamento")
                
        except Exception as e:
            print(f"  ❌ Erro ao processar {os.path.basename(outflow_file)}: {e}")
            continue
    
    if not all_outflow_data:
        print("\n❌ Nenhum arquivo de saída foi processado com sucesso!")
        return None
    
    # Combina todos os dados de saída
    print(f"\nCombinando {len(all_outflow_data)} arquivos de saída...")
    df_all_outflows = pd.concat(all_outflow_data, ignore_index=True)
    print(f"Total de linhas de saída: {len(df_all_outflows)}")
    
    # Processa a entrada
    print("\nProcessando entrada...")
    df_entrada_processed = processar_dados(df_entrada, 'Planilha_Entradas.xls')
    print(f"Entrada processada: {len(df_entrada_processed)} linhas")
    
    # Combina entrada e saída
    df_combined = pd.concat([df_entrada_processed, df_all_outflows], ignore_index=True)
    print(f"Dados combinados: {len(df_combined)} linhas")
    
    # Executa a análise
    print("\nExecutando análise de eventos de negócio...")
    result = identify_key_business_events(df_combined, top_n=10)
    
    print("\n" + "="*60)
    print("RECEITAS IDENTIFICADAS:")
    print("="*60)
    for i, inflow in enumerate(result['key_inflows'], 1):
        print(f"{i}. {inflow['name']}")
        print(f"   Total: R$ {inflow['total_amount']:.2f}")
        print(f"   Frequência: {inflow['frequency']} transações")
        if 'quantity' in inflow:
            print(f"   Quantidade: {inflow['quantity']:.1f} unidades")
        print()
    
    print("="*60)
    print("CUSTOS IDENTIFICADOS:")
    print("="*60)
    for i, outflow in enumerate(result['key_outflows'], 1):
        print(f"{i}. {outflow['name']}")
        print(f"   Total: R$ {outflow['total_amount']:.2f}")
        print(f"   Frequência: {outflow['frequency']} transações")
        print()
    
    # Verifica se os fornecedores estão aparecendo corretamente
    print("="*60)
    print("VERIFICAÇÃO DOS FORNECEDORES:")
    print("="*60)
    
    fornecedores_corretos = True
    fornecedores_numericos = 0
    
    for outflow in result['key_outflows']:
        if outflow['name'].startswith('Custo #'):
            print(f"❌ Fornecedor ainda aparece como: {outflow['name']}")
            fornecedores_corretos = False
            fornecedores_numericos += 1
        else:
            print(f"✅ Fornecedor identificado corretamente: {outflow['name']}")
    
    print(f"\nResumo:")
    print(f"  - Fornecedores corretos: {len(result['key_outflows']) - fornecedores_numericos}")
    print(f"  - Fornecedores numéricos: {fornecedores_numericos}")
    
    if fornecedores_corretos:
        print("\n✅ Todos os fornecedores foram identificados corretamente!")
    else:
        print(f"\n❌ Ainda há {fornecedores_numericos} fornecedores aparecendo como 'Custo #valor'")
    
    return result

def main():
    """Executa o teste."""
    try:
        result = test_all_outflow_files()
        
        if result:
            print("\n" + "="*80)
            print("TESTE CONCLUÍDO COM SUCESSO!")
            print("="*80)
        else:
            print("\n" + "="*80)
            print("TESTE FALHOU!")
            print("="*80)
        
        return result is not None
        
    except Exception as e:
        print(f"❌ ERRO: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)
    else:
        print("\n✅ Teste concluído!")
