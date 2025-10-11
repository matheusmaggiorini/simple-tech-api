# test_business_event_improvements.py
# Script para testar as melhorias na análise de eventos de negócio

import pandas as pd
import sys
import os

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from core.business_event_analyzer import identify_key_business_events
from core.data_processing import processar_descricao_multiplos_produtos

def test_cost_identification():
    """Testa a melhoria na identificação de itens de custo."""
    print("="*60)
    print("TESTE: Identificação de Itens de Custo")
    print("="*60)
    
    # Cria dados de teste com diferentes tipos de descrições de custo
    test_data = {
        'data': ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05'],
        'descricao': ['Fornecedor ABC', '123.45', 'Pagamento PIX', '456.78', 'Aluguel'],
        'fornecedor': ['Fornecedor ABC', '123.45', 'Pagamento PIX', '456.78', 'Aluguel'],
        'forma': ['PIX', 'Dinheiro', 'Cartão', 'Transferência', 'Débito'],
        'saida': [100.0, 123.45, 200.0, 456.78, 800.0],
        'entrada': [0, 0, 0, 0, 0],
        'categoria': ['Fornecedor', 'Outros', 'Pagamento', 'Outros', 'Aluguel']
    }
    
    df = pd.DataFrame(test_data)
    df['data'] = pd.to_datetime(df['data'])
    
    print("Dados de teste:")
    print(df[['descricao', 'fornecedor', 'saida']].to_string())
    print()
    
    # Testa a análise de eventos
    result = identify_key_business_events(df, top_n=5)
    
    print("Resultado da análise de custos:")
    for outflow in result['key_outflows']:
        print(f"  {outflow['name']}: R$ {outflow['total_amount']:.2f} ({outflow['frequency']} transações)")
    
    print()
    return result

def test_revenue_allocation():
    """Testa a melhoria na alocação de valores para receitas."""
    print("="*60)
    print("TESTE: Alocação de Valores para Receitas")
    print("="*60)
    
    # Cria dados de teste com diferentes tipos de descrições de receita
    test_data = {
        'data': ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04'],
        'descricao': [
            '2 X PRODUTO A',
            '1 X PRODUTO B\n3 X PRODUTO C',
            '5 X PRODUTO A',
            '2 X PRODUTO B\n1 X PRODUTO A\n4 X PRODUTO C'
        ],
        'entrada': [200.0, 500.0, 500.0, 800.0],
        'saida': [0, 0, 0, 0],
        'categoria': ['Venda', 'Venda', 'Venda', 'Venda']
    }
    
    df = pd.DataFrame(test_data)
    df['data'] = pd.to_datetime(df['data'])
    
    print("Dados de teste:")
    for i, row in df.iterrows():
        print(f"  {row['descricao']} -> R$ {row['entrada']:.2f}")
    print()
    
    # Testa a análise de eventos
    result = identify_key_business_events(df, top_n=5)
    
    print("Resultado da análise de receitas:")
    for inflow in result['key_inflows']:
        print(f"  {inflow['name']}: R$ {inflow['total_amount']:.2f} ({inflow['frequency']} transações, {inflow['total_quantity']} unidades)")
    
    print()
    return result

def test_multiple_products_processing():
    """Testa especificamente a função de processamento de múltiplos produtos."""
    print("="*60)
    print("TESTE: Processamento de Múltiplos Produtos")
    print("="*60)
    
    # Testa diferentes cenários
    test_cases = [
        {
            'descricao': '2 X PRODUTO A\n3 X PRODUTO B',
            'valor_total': 500.0,
            'precos_conhecidos': {'PRODUTO A': 100.0, 'PRODUTO B': 100.0}
        },
        {
            'descricao': '5 X PRODUTO A\n2 X PRODUTO B',
            'valor_total': 700.0,
            'precos_conhecidos': {'PRODUTO A': 100.0}  # Só A tem preço conhecido
        },
        {
            'descricao': '3 X PRODUTO C\n4 X PRODUTO D',
            'valor_total': 600.0,
            'precos_conhecidos': {}  # Nenhum preço conhecido
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"Caso {i}:")
        print(f"  Descrição: {case['descricao']}")
        print(f"  Valor total: R$ {case['valor_total']:.2f}")
        print(f"  Preços conhecidos: {case['precos_conhecidos']}")
        
        resultado = processar_descricao_multiplos_produtos(
            case['descricao'], 
            case['valor_total'], 
            case['precos_conhecidos']
        )
        
        print("  Resultado:")
        total_alocado = 0
        for qtd, produto, valor in resultado:
            print(f"    {qtd} x {produto}: R$ {valor:.2f}")
            total_alocado += valor
        
        print(f"  Total alocado: R$ {total_alocado:.2f}")
        print(f"  Diferença: R$ {abs(case['valor_total'] - total_alocado):.2f}")
        print()

def test_edge_cases():
    """Testa casos extremos e situações especiais."""
    print("="*60)
    print("TESTE: Casos Extremos")
    print("="*60)
    
    # Caso 1: Descrição vazia
    print("Caso 1: Descrição vazia")
    resultado = processar_descricao_multiplos_produtos("", 100.0, {})
    print(f"  Resultado: {resultado}")
    print()
    
    # Caso 2: Apenas números
    print("Caso 2: Apenas números")
    resultado = processar_descricao_multiplos_produtos("123.45", 100.0, {})
    print(f"  Resultado: {resultado}")
    print()
    
    # Caso 3: Múltiplos produtos com preços que excedem o total
    print("Caso 3: Preços que excedem o total")
    resultado = processar_descricao_multiplos_produtos(
        "2 X PRODUTO A\n1 X PRODUTO B", 
        100.0, 
        {'PRODUTO A': 60.0, 'PRODUTO B': 50.0}
    )
    print(f"  Resultado: {resultado}")
    print()

def main():
    """Executa todos os testes."""
    print("INICIANDO TESTES DAS MELHORIAS NA ANÁLISE DE EVENTOS")
    print("="*80)
    
    try:
        # Teste 1: Identificação de custos
        cost_result = test_cost_identification()
        
        # Teste 2: Alocação de receitas
        revenue_result = test_revenue_allocation()
        
        # Teste 3: Processamento de múltiplos produtos
        test_multiple_products_processing()
        
        # Teste 4: Casos extremos
        test_edge_cases()
        
        print("="*80)
        print("TODOS OS TESTES CONCLUÍDOS COM SUCESSO!")
        print("="*80)
        
        # Resumo dos resultados
        print("\nRESUMO DOS RESULTADOS:")
        print(f"Custos identificados: {len(cost_result['key_outflows'])}")
        print(f"Receitas identificadas: {len(revenue_result['key_inflows'])}")
        
        return True
        
    except Exception as e:
        print(f"❌ ERRO durante os testes: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)
    else:
        print("\n✅ Todos os testes passaram com sucesso!")
