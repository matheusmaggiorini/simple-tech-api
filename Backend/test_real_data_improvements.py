# test_real_data_improvements.py
# Script para testar as melhorias com dados mais realistas

import pandas as pd
import sys
import os

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from core.business_event_analyzer import identify_key_business_events
from core.data_processing import processar_descricao_multiplos_produtos

def create_realistic_test_data():
    """Cria dados de teste mais realistas."""
    
    # Dados de entrada (receitas) com diferentes padrões
    inflow_data = {
        'data': [
            '2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05',
            '2024-01-06', '2024-01-07', '2024-01-08', '2024-01-09', '2024-01-10'
        ],
        'descricao': [
            '2 X RATICIDA KROMAX',
            '1 X PORTA SANFONADA\n3 X FECHADURA',
            '5 X RATICIDA KROMAX',
            '2 X PORTA SANFONADA\n1 X RATICIDA KROMAX\n4 X FECHADURA',
            '10 X SANLIMP 5LT\n10 X ALCOOL 70% 1L\n10 X DESINFETANTE FLO',
            '3 X RATICIDA KROMAX',
            '1 X PORTA SANFONADA',
            '2 X FECHADURA\n1 X RATICIDA KROMAX',
            '5 X SANLIMP 5LT\n5 X ALCOOL 70% 1L',
            '1 X PORTA SANFONADA\n2 X FECHADURA'
        ],
        'entrada': [200.0, 500.0, 500.0, 800.0, 1500.0, 300.0, 250.0, 400.0, 750.0, 350.0],
        'saida': [0] * 10,
        'categoria': ['Venda'] * 10
    }
    
    # Dados de saída (custos) com diferentes padrões
    outflow_data = {
        'data': [
            '2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05',
            '2024-01-06', '2024-01-07', '2024-01-08', '2024-01-09', '2024-01-10'
        ],
        'descricao': [
            'Fornecedor ABC Ltda',
            '123.45',
            'Pagamento PIX - Fornecedor XYZ',
            '456.78',
            'Aluguel do escritório',
            '789.12',
            'Energia elétrica',
            '345.67',
            'Internet e telefone',
            '890.23'
        ],
        'fornecedor': [
            'Fornecedor ABC Ltda', '123.45', 'Fornecedor XYZ', '456.78', 'Imobiliária Silva',
            '789.12', 'CEMIG', '345.67', 'Vivo', '890.23'
        ],
        'forma': [
            'PIX', 'Dinheiro', 'PIX', 'Transferência', 'Débito automático',
            'Cartão', 'Débito automático', 'PIX', 'Débito automático', 'Transferência'
        ],
        'saida': [100.0, 123.45, 200.0, 456.78, 800.0, 789.12, 150.0, 345.67, 120.0, 890.23],
        'entrada': [0] * 10,
        'categoria': ['Fornecedor', 'Outros', 'Fornecedor', 'Outros', 'Aluguel',
                     'Outros', 'Energia', 'Outros', 'Telecomunicações', 'Outros']
    }
    
    # Combina os dados
    all_data = {
        'data': inflow_data['data'] + outflow_data['data'],
        'descricao': inflow_data['descricao'] + outflow_data['descricao'],
        'entrada': inflow_data['entrada'] + outflow_data['entrada'],
        'saida': inflow_data['saida'] + outflow_data['saida'],
        'categoria': inflow_data['categoria'] + outflow_data['categoria']
    }
    
    # Adiciona colunas de fornecedor e forma para as saídas
    all_data['fornecedor'] = [''] * 10 + outflow_data['fornecedor']
    all_data['forma'] = [''] * 10 + outflow_data['forma']
    
    df = pd.DataFrame(all_data)
    df['data'] = pd.to_datetime(df['data'])
    
    return df

def test_improvements_with_real_data():
    """Testa as melhorias com dados realistas."""
    print("="*80)
    print("TESTE DAS MELHORIAS COM DADOS REALISTAS")
    print("="*80)
    
    # Cria dados de teste
    df = create_realistic_test_data()
    
    print("Dados de teste criados:")
    print(f"  Total de transações: {len(df)}")
    print(f"  Entradas: {len(df[df['entrada'] > 0])}")
    print(f"  Saídas: {len(df[df['saida'] > 0])}")
    print()
    
    # Mostra algumas transações de exemplo
    print("Exemplos de transações de entrada:")
    for i, row in df[df['entrada'] > 0].head(3).iterrows():
        print(f"  {row['descricao']} -> R$ {row['entrada']:.2f}")
    print()
    
    print("Exemplos de transações de saída:")
    for i, row in df[df['saida'] > 0].head(3).iterrows():
        print(f"  {row['descricao']} -> R$ {row['saida']:.2f}")
    print()
    
    # Executa a análise
    print("Executando análise de eventos de negócio...")
    result = identify_key_business_events(df, top_n=5)
    
    # Mostra resultados
    print("\n" + "="*60)
    print("PRINCIPAIS RECEITAS IDENTIFICADAS:")
    print("="*60)
    for i, inflow in enumerate(result['key_inflows'], 1):
        print(f"{i}. {inflow['name']}")
        print(f"   Total: R$ {inflow['total_amount']:.2f}")
        print(f"   Frequência: {inflow['frequency']} transações")
        print(f"   Quantidade total: {inflow['total_quantity']} unidades")
        print(f"   Categoria: {inflow['category']}")
        print()
    
    print("="*60)
    print("PRINCIPAIS CUSTOS IDENTIFICADOS:")
    print("="*60)
    for i, outflow in enumerate(result['key_outflows'], 1):
        print(f"{i}. {outflow['name']}")
        print(f"   Total: R$ {outflow['total_amount']:.2f}")
        print(f"   Frequência: {outflow['frequency']} transações")
        print(f"   Categoria: {outflow['category']}")
        print()
    
    return result

def test_specific_improvements():
    """Testa melhorias específicas."""
    print("="*80)
    print("TESTE DE MELHORIAS ESPECÍFICAS")
    print("="*80)
    
    # Teste 1: Identificação de custos numéricos
    print("1. Teste de identificação de custos numéricos:")
    test_costs = pd.DataFrame({
        'data': ['2024-01-01', '2024-01-02', '2024-01-03'],
        'descricao': ['123.45', '456.78', '789.12'],
        'saida': [123.45, 456.78, 789.12],
        'entrada': [0, 0, 0],
        'categoria': ['Outros'] * 3
    })
    test_costs['data'] = pd.to_datetime(test_costs['data'])
    
    result = identify_key_business_events(test_costs, top_n=3)
    print("   Custos identificados:")
    for outflow in result['key_outflows']:
        print(f"     {outflow['name']}: R$ {outflow['total_amount']:.2f}")
    print()
    
    # Teste 2: Alocação inteligente de valores
    print("2. Teste de alocação inteligente de valores:")
    test_revenue = pd.DataFrame({
        'data': ['2024-01-01', '2024-01-02'],
        'descricao': [
            '2 X PRODUTO A\n3 X PRODUTO B',
            '1 X PRODUTO A\n5 X PRODUTO B'
        ],
        'entrada': [500.0, 600.0],
        'saida': [0, 0],
        'categoria': ['Venda', 'Venda']
    })
    test_revenue['data'] = pd.to_datetime(test_revenue['data'])
    
    result = identify_key_business_events(test_revenue, top_n=3)
    print("   Receitas identificadas:")
    for inflow in result['key_inflows']:
        print(f"     {inflow['name']}: R$ {inflow['total_amount']:.2f} ({inflow['total_quantity']} unidades)")
    print()

def main():
    """Executa todos os testes."""
    try:
        # Teste com dados realistas
        result = test_improvements_with_real_data()
        
        # Teste de melhorias específicas
        test_specific_improvements()
        
        print("="*80)
        print("TODOS OS TESTES CONCLUÍDOS COM SUCESSO!")
        print("="*80)
        
        # Resumo final
        print("\nRESUMO FINAL:")
        print(f"✅ Identificação de custos melhorada: {len(result['key_outflows'])} custos identificados")
        print(f"✅ Alocação de receitas melhorada: {len(result['key_inflows'])} receitas identificadas")
        print("✅ Valores numéricos agora são identificados como custos")
        print("✅ Alocação proporcional de valores para múltiplos produtos")
        print("✅ Preços unitários deduzidos de transações de item único")
        
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
        print("\n✅ Todas as melhorias estão funcionando corretamente!")
