#!/usr/bin/env python3
"""
Teste para verificar se o endpoint retorna apenas os 5 principais de cada categoria.
"""

import requests
import json
import sys
import os

def test_endpoint_top_5():
    """Testa se o endpoint retorna apenas os 5 principais de cada categoria."""
    
    print("Testando endpoint /api/simulations/key-business-events (top 5)...")
    
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
            if 'key_outflows' in data and 'key_inflows' in data:
                outflows = data['key_outflows']
                inflows = data['key_inflows']
                
                print(f"\n=== RECEITAS (key_inflows) ===")
                print(f"Encontrados {len(inflows)} receitas principais:")
                
                for i, inflow in enumerate(inflows, 1):
                    name = inflow.get('name', 'N/A')
                    total_amount = inflow.get('total_amount', 0)
                    frequency = inflow.get('frequency', 0)
                    
                    print(f"  {i}. {name} - R$ {total_amount:.2f} ({frequency} transações)")
                
                print(f"\n=== CUSTOS (key_outflows) ===")
                print(f"Encontrados {len(outflows)} custos principais:")
                
                for i, outflow in enumerate(outflows, 1):
                    name = outflow.get('name', 'N/A')
                    total_amount = outflow.get('total_amount', 0)
                    frequency = outflow.get('frequency', 0)
                    
                    print(f"  {i}. {name} - R$ {total_amount:.2f} ({frequency} transações)")
                
                # Verifica se há exatamente 5 de cada categoria
                if len(inflows) <= 5 and len(outflows) <= 5:
                    print(f"\nSUCESSO: Retornando {len(inflows)} receitas e {len(outflows)} custos (maximo 5 de cada)")
                    
                    # Verifica se há nomes genéricos nos custos
                    generic_names = [outflow['name'] for outflow in outflows if outflow['name'].startswith('Custo #')]
                    
                    if generic_names:
                        print(f"ERRO: Ainda ha nomes genericos nos custos: {generic_names}")
                        return False
                    else:
                        print("SUCESSO: Todos os nomes de custos sao de fornecedores reais!")
                        return True
                else:
                    print(f"ERRO: Retornando {len(inflows)} receitas e {len(outflows)} custos (deveria ser maximo 5 de cada)")
                    return False
            else:
                print("ERRO: Resposta não contém 'key_outflows' e 'key_inflows'")
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

def main():
    """Executa o teste."""
    
    print("Iniciando teste do endpoint (top 5 de cada categoria)...")
    
    # Teste do endpoint
    endpoint_test_passed = test_endpoint_top_5()
    
    print("\nResumo do teste:")
    print(f"Endpoint funcionando corretamente: {'SIM' if endpoint_test_passed else 'NÃO'}")
    
    if endpoint_test_passed:
        print("\nSUCESSO: O endpoint esta retornando apenas os 5 principais de cada categoria!")
        return True
    else:
        print("\nFALHA: O endpoint ainda nao esta funcionando corretamente.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
