#!/usr/bin/env python3
"""
Teste para verificar se o endpoint /api/simulations/key-business-events
está carregando dados reais das planilhas de saída.
"""

import requests
import json
import sys
import os

def test_endpoint_with_real_data():
    """Testa o endpoint com dados reais das planilhas."""
    
    print("Testando endpoint /api/simulations/key-business-events...")
    
    try:
        # URL da API
        api_url = "http://localhost:8000/api/simulations/key-business-events"
        
        print(f"Fazendo requisição para: {api_url}")
        
        # Faz a requisição GET
        response = requests.get(api_url, timeout=30)
        
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
                    print(f"\nERRO: Ainda há nomes genéricos: {generic_names}")
                    return False
                else:
                    print("\nSUCESSO: Todos os nomes são de fornecedores reais!")
                    
                    # Verifica se há nomes esperados das planilhas
                    supplier_names = [outflow['name'] for outflow in outflows]
                    expected_suppliers = ['Obramax', 'Eletroleste', 'Cimeprimo', 'Sodimac', 'Docol']
                    
                    found_suppliers = [name for name in expected_suppliers if name in supplier_names]
                    if found_suppliers:
                        print(f"SUCESSO: Encontrados fornecedores esperados: {found_suppliers}")
                    else:
                        print(f"AVISO: Nenhum fornecedor esperado encontrado. Nomes encontrados: {supplier_names[:5]}")
                    
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

def test_data_availability():
    """Testa o endpoint de disponibilidade de dados."""
    
    print("\nTestando disponibilidade de dados...")
    
    try:
        api_url = "http://localhost:8000/api/simulations/data-availability"
        response = requests.get(api_url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"Status dos dados: {data}")
            return data.get('has_real_data', False)
        else:
            print(f"ERRO: Status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"ERRO ao verificar disponibilidade: {str(e)}")
        return False

def main():
    """Executa todos os testes."""
    
    print("Iniciando testes do endpoint corrigido...")
    
    # Teste 1: Verificar disponibilidade de dados
    has_real_data = test_data_availability()
    
    # Teste 2: Testar endpoint principal
    endpoint_test_passed = test_endpoint_with_real_data()
    
    print("\nResumo dos testes:")
    print(f"Dados reais disponíveis: {'SIM' if has_real_data else 'NÃO'}")
    print(f"Endpoint funcionando: {'SIM' if endpoint_test_passed else 'NÃO'}")
    
    if endpoint_test_passed:
        print("\nSUCESSO: O endpoint está funcionando corretamente!")
        print("Os nomes dos fornecedores estão sendo exibidos corretamente.")
        return True
    else:
        print("\nFALHA: O endpoint ainda não está funcionando corretamente.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
