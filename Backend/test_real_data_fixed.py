# test_real_data_fixed.py
# Teste com dados reais após correção

import pandas as pd
import sys
import os

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from core.business_event_analyzer import identify_key_business_events
from core.data_processing import processar_dados

def test_real_data_fixed():
    """Testa com dados reais após correção."""
    print("="*80)
    print("TESTE COM DADOS REAIS APÓS CORREÇÃO")
    print("="*80)
    
    # Carrega os dados reais
    try:
        # Carrega planilha de entrada
        df_entrada = pd.read_excel('data/Planilha_Entradas.xls')
        print(f"Planilha de entrada carregada: {len(df_entrada)} linhas")
        
        # Carrega planilha de saída
        df_saida = pd.read_excel('data/yUuUeCnbiOsksnUd.xlsx')
        print(f"Planilha de saída carregada: {len(df_saida)} linhas")
        
        # Processa os dados
        print("\nProcessando dados...")
        
        # Processa entrada
        df_entrada_processed = processar_dados(df_entrada, 'Planilha_Entradas.xls')
        print(f"Entrada processada: {len(df_entrada_processed)} linhas")
        
        # Processa saída
        df_saida_processed = processar_dados(df_saida, 'yUuUeCnbiOsksnUd.xlsx')
        print(f"Saída processada: {len(df_saida_processed)} linhas")
        
        # Combina os dados
        df_combined = pd.concat([df_entrada_processed, df_saida_processed], ignore_index=True)
        
        print(f"Dados combinados: {len(df_combined)} linhas")
        print(f"Colunas: {list(df_combined.columns)}")
        
        # Executa a análise
        print("\nExecutando análise de eventos de negócio...")
        result = identify_key_business_events(df_combined, top_n=5)
        
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
        for outflow in result['key_outflows']:
            if outflow['name'].startswith('Custo #'):
                print(f"❌ Fornecedor ainda aparece como: {outflow['name']}")
                fornecedores_corretos = False
            else:
                print(f"✅ Fornecedor identificado corretamente: {outflow['name']}")
        
        if fornecedores_corretos:
            print("\n✅ Todos os fornecedores foram identificados corretamente!")
        else:
            print("\n❌ Ainda há fornecedores aparecendo como 'Custo #valor'")
        
        return result
        
    except Exception as e:
        print(f"❌ ERRO: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Executa o teste."""
    try:
        result = test_real_data_fixed()
        
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
