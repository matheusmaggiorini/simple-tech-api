#!/usr/bin/env python3
"""
Teste para validar a correção da identificação de nomes de fornecedores
nas planilhas de saída.
"""

import pandas as pd
import sys
import os

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from core.business_event_analyzer import identify_key_business_events
from core.data_processing import processar_dados

def test_supplier_name_extraction():
    """Testa a extração de nomes de fornecedores das planilhas de saída."""
    
    print("Testando extração de nomes de fornecedores...")
    
    # Cria dados de teste simulando a estrutura das planilhas de saída
    test_data = {
        'data': ['01/01/2024', '01/01/2024', '02/01/2024', '02/01/2024', '03/01/2024'],
        'descricao': ['Obramax', 'Eletroleste', 'Cimeprimo', 'Sodimac', 'Docol'],
        'saida': [714.00, 242.40, 556.62, 1307.28, 656.82],
        'entrada': [0, 0, 0, 0, 0],
        'categoria': ['outros', 'outros', 'outros', 'outros', 'outros']
    }
    
    df_test = pd.DataFrame(test_data)
    print(f"Dados de teste criados: {len(df_test)} linhas")
    print("Colunas:", df_test.columns.tolist())
    print("Primeiras linhas:")
    print(df_test.head())
    
    # Testa a função identify_key_business_events
    try:
        result = identify_key_business_events(df_test, top_n=5)
        
        print("\nResultado da análise de eventos de negócio:")
        print("Key Outflows (Custos):")
        for i, outflow in enumerate(result['key_outflows'], 1):
            print(f"  {i}. {outflow['name']} - R$ {outflow['total_amount']:.2f} ({outflow['frequency']} transações)")
        
        # Verifica se os nomes dos fornecedores estão corretos
        supplier_names = [outflow['name'] for outflow in result['key_outflows']]
        expected_suppliers = ['Obramax', 'Eletroleste', 'Cimeprimo', 'Sodimac', 'Docol']
        
        print(f"\nVerificação:")
        print(f"Nomes extraídos: {supplier_names}")
        print(f"Nomes esperados: {expected_suppliers}")
        
        # Verifica se não há nomes genéricos como "Custo #"
        generic_names = [name for name in supplier_names if name.startswith('Custo #')]
        if generic_names:
            print(f"ERRO: Encontrados nomes genéricos: {generic_names}")
            return False
        else:
            print("Nenhum nome genérico encontrado!")
            
        # Verifica se os fornecedores esperados estão presentes
        missing_suppliers = [supplier for supplier in expected_suppliers if supplier not in supplier_names]
        if missing_suppliers:
            print(f"Fornecedores não encontrados: {missing_suppliers}")
        else:
            print("Todos os fornecedores esperados foram identificados!")
            
        return True
        
    except Exception as e:
        print(f"ERRO na análise: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_real_data_processing():
    """Testa o processamento de dados reais das planilhas de saída."""
    
    print("\nTestando processamento de dados reais...")
    
    try:
        # Carrega uma planilha real de saída
        df_real = pd.read_excel('data/dados_de_saida/Janeiro_Normalizado.xlsx')
        print(f"Planilha real carregada: {len(df_real)} linhas")
        print("Colunas originais:", df_real.columns.tolist())
        print("Primeiras linhas:")
        print(df_real.head())
        
        # Processa os dados
        df_processed = processar_dados(df_real, filename='Janeiro_Normalizado.xlsx')
        print(f"\nDados processados: {len(df_processed)} linhas")
        print("Colunas processadas:", df_processed.columns.tolist())
        
        # Verifica se a coluna 'saida' contém valores monetários
        if 'saida' in df_processed.columns:
            print(f"Valores na coluna 'saida': {df_processed['saida'].sum():.2f}")
            print("Primeiros valores de 'saida':", df_processed['saida'].head().tolist())
        
        # Verifica se a coluna 'descricao' contém nomes de fornecedores
        if 'descricao' in df_processed.columns:
            unique_descriptions = df_processed['descricao'].unique()
            print(f"Nomes únicos na descrição: {len(unique_descriptions)}")
            print("Primeiros nomes:", unique_descriptions[:5].tolist())
        
        # Testa a análise de eventos de negócio
        result = identify_key_business_events(df_processed, top_n=5)
        
        print("\nAnálise de eventos de negócio com dados reais:")
        print("Key Outflows (Custos):")
        for i, outflow in enumerate(result['key_outflows'], 1):
            print(f"  {i}. {outflow['name']} - R$ {outflow['total_amount']:.2f} ({outflow['frequency']} transações)")
        
        # Verifica se os nomes são de fornecedores reais
        supplier_names = [outflow['name'] for outflow in result['key_outflows']]
        generic_names = [name for name in supplier_names if name.startswith('Custo #')]
        
        if generic_names:
            print(f"ERRO: Encontrados nomes genéricos: {generic_names}")
            return False
        else:
            print("Todos os nomes são de fornecedores reais!")
            return True
            
    except Exception as e:
        print(f"ERRO no processamento de dados reais: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Executa todos os testes."""
    
    print("Iniciando testes de correção de nomes de fornecedores...")
    
    # Teste 1: Dados simulados
    test1_passed = test_supplier_name_extraction()
    
    # Teste 2: Dados reais
    test2_passed = test_real_data_processing()
    
    print("\nResumo dos testes:")
    print(f"Teste 1 (dados simulados): {'PASSOU' if test1_passed else 'FALHOU'}")
    print(f"Teste 2 (dados reais): {'PASSOU' if test2_passed else 'FALHOU'}")
    
    if test1_passed and test2_passed:
        print("\nTodos os testes passaram! A correção está funcionando corretamente.")
        return True
    else:
        print("\nAlguns testes falharam. Verifique os logs acima.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
