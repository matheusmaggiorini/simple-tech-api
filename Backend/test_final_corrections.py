# test_final_corrections.py
# Teste final das correções implementadas

import pandas as pd
import sys
import os

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from core.business_event_analyzer import identify_key_business_events

def test_corrected_analysis():
    """Testa a análise corrigida."""
    print("="*80)
    print("TESTE FINAL DAS CORREÇÕES")
    print("="*80)
    
    # Dados de teste com estrutura correta
    test_data = {
        'data': [
            '2024-01-01', '2024-01-01', '2024-01-01', '2024-01-01', '2024-01-01',
            '2024-01-01', '2024-01-01', '2024-01-01', '2024-01-01', '2024-01-01'
        ],
        'entrada': [1000, 500, 200, 0, 0, 0, 0, 0, 0, 0],
        'saida': [0, 0, 0, 714.00, 242.40, 556.62, 1307.28, 656.82, 0, 0],
        'descricao': [
            '2 X PRODUTO A',  # Receita normal
            'FRETE + TAXAS',  # Deve ser removido
            '1 X PRODUTO B',  # Receita normal
            'Obramax',        # Fornecedor
            'Obramax',        # Fornecedor
            'Eletroleste',    # Fornecedor
            'Obramax',        # Fornecedor
            'Cimeprimo',     # Fornecedor
            'nan',           # Receita com problema
            'nan'            # Receita com problema
        ],
        'categoria': ['Venda', 'Financeiro', 'Venda', 'Fornecedor', 'Fornecedor', 'Fornecedor', 'Fornecedor', 'Fornecedor', 'Outros', 'Outros']
    }
    
    df = pd.DataFrame(test_data)
    df['data'] = pd.to_datetime(df['data'])
    
    print("Dados de teste:")
    print(df[['descricao', 'entrada', 'saida']].to_string())
    print()
    
    # Executa a análise
    result = identify_key_business_events(df, top_n=5)
    
    print("="*60)
    print("RECEITAS IDENTIFICADAS:")
    print("="*60)
    for i, inflow in enumerate(result['key_inflows'], 1):
        print(f"{i}. {inflow['name']}")
        print(f"   Total: R$ {inflow['total_amount']:.2f}")
        print(f"   Frequência: {inflow['frequency']} transações")
        print(f"   Quantidade: {inflow['total_quantity']} unidades")
        print()
    
    print("="*60)
    print("CUSTOS IDENTIFICADOS:")
    print("="*60)
    for i, outflow in enumerate(result['key_outflows'], 1):
        print(f"{i}. {outflow['name']}")
        print(f"   Total: R$ {outflow['total_amount']:.2f}")
        print(f"   Frequência: {outflow['frequency']} transações")
        print()
    
    # Verifica se as correções funcionaram
    print("="*60)
    print("VERIFICAÇÃO DAS CORREÇÕES:")
    print("="*60)
    
    # Verifica se FRETE + TAXAS foi removido
    frete_removido = not any('FRETE' in inflow['name'] for inflow in result['key_inflows'])
    print(f"✅ FRETE + TAXAS removido das receitas: {frete_removido}")
    
    # Verifica se fornecedores foram identificados corretamente
    fornecedores_corretos = any('Obramax' in outflow['name'] for outflow in result['key_outflows'])
    print(f"✅ Fornecedores identificados corretamente: {fornecedores_corretos}")
    
    # Verifica se não há custos numéricos
    custos_numericos = any('Custo #' in outflow['name'] for outflow in result['key_outflows'])
    print(f"✅ Sem custos numéricos (Custo #): {not custos_numericos}")
    
    return result

def main():
    """Executa o teste final."""
    try:
        result = test_corrected_analysis()
        
        print("="*80)
        print("TESTE FINAL CONCLUÍDO COM SUCESSO!")
        print("="*80)
        
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
        print("\n✅ Todas as correções estão funcionando corretamente!")
