# test_fix_outflow.py
# Teste específico para corrigir o processamento de saídas

import pandas as pd
import sys
import os

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from core.business_event_analyzer import identify_key_business_events

def test_simple_outflow():
    """Testa com dados simples de saída."""
    print("="*80)
    print("TESTE SIMPLES DE SAÍDAS")
    print("="*80)
    
    # Cria dados de teste simples
    test_data = {
        'data': ['2024-01-01', '2024-01-01', '2024-01-01', '2024-01-01', '2024-01-01'],
        'saida': [714.00, 242.40, 556.62, 1307.28, 656.82],
        'entrada': [0, 0, 0, 0, 0],
        'descricao': ['Obramax', 'Obramax', 'Eletroleste', 'Obramax', 'Cimeprimo'],
        'categoria': ['Fornecedor', 'Fornecedor', 'Fornecedor', 'Fornecedor', 'Fornecedor']
    }
    
    df = pd.DataFrame(test_data)
    df['data'] = pd.to_datetime(df['data'])
    
    print("Dados de teste:")
    print(df.to_string())
    print()
    
    # Testa a análise
    result = identify_key_business_events(df, top_n=5)
    
    print("Resultado da análise:")
    print("Custos identificados:")
    for outflow in result['key_outflows']:
        print(f"  {outflow['name']}: R$ {outflow['total_amount']:.2f} ({outflow['frequency']} transações)")
    
    return result

def test_with_real_structure():
    """Testa com a estrutura real das planilhas."""
    print("="*80)
    print("TESTE COM ESTRUTURA REAL")
    print("="*80)
    
    # Simula a estrutura real: SAIDA (fornecedor), VALOR (valor), Data
    test_data = {
        'data': ['2024-01-01', '2024-01-01', '2024-01-01', '2024-01-01', '2024-01-01'],
        'saida': [714.00, 242.40, 556.62, 1307.28, 656.82],  # Valores monetários
        'entrada': [0, 0, 0, 0, 0],
        'descricao': ['Obramax', 'Obramax', 'Eletroleste', 'Obramax', 'Cimeprimo'],  # Nomes dos fornecedores
        'categoria': ['Fornecedor', 'Fornecedor', 'Fornecedor', 'Fornecedor', 'Fornecedor']
    }
    
    df = pd.DataFrame(test_data)
    df['data'] = pd.to_datetime(df['data'])
    
    print("Dados de teste (estrutura real):")
    print(df.to_string())
    print()
    
    # Testa a análise
    result = identify_key_business_events(df, top_n=5)
    
    print("Resultado da análise:")
    print("Custos identificados:")
    for outflow in result['key_outflows']:
        print(f"  {outflow['name']}: R$ {outflow['total_amount']:.2f} ({outflow['frequency']} transações)")
    
    return result

def main():
    """Executa os testes."""
    try:
        # Teste 1: Dados simples
        result1 = test_simple_outflow()
        
        # Teste 2: Estrutura real
        result2 = test_with_real_structure()
        
        print("="*80)
        print("TESTES CONCLUÍDOS")
        print("="*80)
        
        print(f"Teste 1 - Custos identificados: {len(result1['key_outflows'])}")
        print(f"Teste 2 - Custos identificados: {len(result2['key_outflows'])}")
        
        return True
        
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
        print("\n✅ Testes concluídos com sucesso!")
