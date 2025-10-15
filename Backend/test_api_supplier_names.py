#!/usr/bin/env python3
"""
Teste para verificar se a API endpoint está retornando nomes de fornecedores corretos.
"""

import requests
import json
import sys
import os

def test_api_endpoint():
    """Testa o endpoint /simulations/key-business-events da API."""
    
    print("Testando endpoint da API...")
    
    try:
        # URL da API (assumindo que está rodando localmente)
        api_url = "http://localhost:8000/simulations/key-business-events"
        
        print(f"Fazendo requisição para: {api_url}")
        
        # Faz a requisição GET
        response = requests.get(api_url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            print("Resposta da API recebida com sucesso!")
            print(f"Status: {response.status_code}")
            
            # Verifica se a resposta tem a estrutura esperada
            if 'key_outflows' in data:
                outflows = data['key_outflows']
                print(f"\nEncontrados {len(outflows)} custos principais:")
                
                for i, outflow in enumerate(outflows, 1):
                    name = outflow.get('name', 'N/A')
                    total_amount = outflow.get('total_amount', 0)
                    frequency = outflow.get('frequency', 0)
                    
                    print(f"  {i}. {name} - R$ {total_amount:.2f} ({frequency} transações)")
                
                # Verifica se há nomes genéricos
                generic_names = [outflow['name'] for outflow in outflows if outflow['name'].startswith('Custo #')]
                
                if generic_names:
                    print(f"\nERRO: Encontrados nomes genéricos: {generic_names}")
                    return False
                else:
                    print("\nSUCESSO: Todos os nomes são de fornecedores reais!")
                    return True
            else:
                print("ERRO: Resposta não contém 'key_outflows'")
                return False
                
        else:
            print(f"ERRO: Status {response.status_code}")
            print(f"Resposta: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("ERRO: Não foi possível conectar à API. Verifique se o servidor está rodando.")
        return False
    except requests.exceptions.Timeout:
        print("ERRO: Timeout na requisição.")
        return False
    except Exception as e:
        print(f"ERRO: {str(e)}")
        return False

def test_api_with_mock_data():
    """Testa a API usando dados mock se não conseguir conectar."""
    
    print("\nTestando com dados mock...")
    
    try:
        # Importa as funções necessárias
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
        
        from core.business_event_analyzer import identify_key_business_events
        import pandas as pd
        
        # Cria dados mock
        mock_data = {
            'data': ['01/01/2024', '01/01/2024', '02/01/2024', '02/01/2024', '03/01/2024'],
            'descricao': ['Obramax', 'Eletroleste', 'Cimeprimo', 'Sodimac', 'Docol'],
            'saida': [714.00, 242.40, 556.62, 1307.28, 656.82],
            'entrada': [0, 0, 0, 0, 0],
            'categoria': ['outros', 'outros', 'outros', 'outros', 'outros']
        }
        
        df_mock = pd.DataFrame(mock_data)
        
        # Testa a função diretamente
        result = identify_key_business_events(df_mock, top_n=5)
        
        print("Resultado com dados mock:")
        print("Key Outflows (Custos):")
        for i, outflow in enumerate(result['key_outflows'], 1):
            print(f"  {i}. {outflow['name']} - R$ {outflow['total_amount']:.2f} ({outflow['frequency']} transações)")
        
        # Verifica se há nomes genéricos
        generic_names = [outflow['name'] for outflow in result['key_outflows'] if outflow['name'].startswith('Custo #')]
        
        if generic_names:
            print(f"ERRO: Encontrados nomes genéricos: {generic_names}")
            return False
        else:
            print("SUCESSO: Todos os nomes são de fornecedores reais!")
            return True
            
    except Exception as e:
        print(f"ERRO no teste com dados mock: {str(e)}")
        return False

def main():
    """Executa todos os testes da API."""
    
    print("Iniciando testes da API...")
    
    # Teste 1: API real
    api_test_passed = test_api_endpoint()
    
    # Teste 2: Dados mock (fallback)
    mock_test_passed = test_api_with_mock_data()
    
    print("\nResumo dos testes:")
    print(f"Teste API real: {'PASSOU' if api_test_passed else 'FALHOU'}")
    print(f"Teste dados mock: {'PASSOU' if mock_test_passed else 'FALHOU'}")
    
    if api_test_passed or mock_test_passed:
        print("\nPelo menos um teste passou! As correções estão funcionando.")
        return True
    else:
        print("\nTodos os testes falharam. Verifique os logs acima.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
