# test_simulation_api.py
# Script para testar a API de simulação de cenários

import requests
import json
import sys

def test_simulation_api():
    """Testa a API de simulação de cenários."""
    
    base_url = "http://127.0.0.1:8000"  # Ajuste conforme necessário
    
    print("="*60)
    print("TESTE DA API DE SIMULAÇÃO DE CENÁRIOS")
    print("="*60)
    
    # Teste 1: Verificar status
    print("\n1. Testando endpoint de status...")
    try:
        response = requests.get(f"{base_url}/api/simulations/status")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            status_data = response.json()
            print("✅ Status OK")
            print(f"Módulo: {status_data.get('module')}")
            print(f"Status: {status_data.get('status')}")
            print(f"Tem dados: {status_data.get('has_data')}")
            print(f"Cenários disponíveis: {status_data.get('available_scenarios')}")
        else:
            print(f"❌ Erro no status: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Não foi possível conectar à API. Verifique se o servidor está rodando.")
        return False
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        return False
    
    # Teste 2: Simulação básica (cenário otimista)
    print("\n2. Testando simulação básica (cenário otimista)...")
    
    payload = {
        "scenario_type": "otimista",
        "seasonality_rules": None
    }
    
    try:
        response = requests.post(
            f"{base_url}/api/simulations/scenario-simulation",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type')}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                print("✅ Simulação básica executada com sucesso")
                print(f"Tipo de cenário: {result.get('scenario_type')}")
                print(f"Sazonalidade aplicada: {result.get('seasonality_applied')}")
                
                # Mostrar resumos
                original = result.get('original_summary', {})
                simulated = result.get('simulated_summary', {})
                
                print(f"\nORIGINAL:")
                print(f"  Receita: R$ {original.get('total_receita', 0):,.2f}")
                print(f"  Custo: R$ {original.get('total_custo', 0):,.2f}")
                print(f"  Fluxo: R$ {original.get('total_fluxo_de_caixa', 0):,.2f}")
                
                print(f"\nSIMULADO (Otimista):")
                print(f"  Receita: R$ {simulated.get('total_receita', 0):,.2f}")
                print(f"  Custo: R$ {simulated.get('total_custo', 0):,.2f}")
                print(f"  Fluxo: R$ {simulated.get('total_fluxo_de_caixa', 0):,.2f}")
                
                print(f"\nDetalhes mensais: {len(result.get('monthly_details', []))} registros")
                
            except json.JSONDecodeError as e:
                print(f"❌ Erro ao decodificar JSON: {e}")
                print(f"Resposta recebida: {response.text[:500]}...")
                return False
                
        else:
            print(f"❌ Erro na simulação básica")
            print(f"Resposta: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Erro inesperado na simulação básica: {e}")
        return False
    
    # Teste 3: Simulação com sazonalidade (cenário pessimista)
    print("\n3. Testando simulação com sazonalidade (cenário pessimista)...")
    
    payload_seasonal = {
        "scenario_type": "pessimista",
        "seasonality_rules": [
            {
                "month": "Dezembro",
                "revenue_change_percentage": 30
            },
            {
                "month": "Janeiro",
                "revenue_change_percentage": -20
            }
        ]
    }
    
    try:
        response = requests.post(
            f"{base_url}/api/simulations/scenario-simulation",
            json=payload_seasonal,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                print("✅ Simulação com sazonalidade executada com sucesso")
                print(f"Tipo de cenário: {result.get('scenario_type')}")
                print(f"Sazonalidade aplicada: {result.get('seasonality_applied')}")
                print(f"Regras de sazonalidade: {result.get('seasonality_rules_count')}")
                
                # Mostrar resumos
                original = result.get('original_summary', {})
                simulated = result.get('simulated_summary', {})
                
                print(f"\nORIGINAL:")
                print(f"  Receita: R$ {original.get('total_receita', 0):,.2f}")
                print(f"  Custo: R$ {original.get('total_custo', 0):,.2f}")
                print(f"  Fluxo: R$ {original.get('total_fluxo_de_caixa', 0):,.2f}")
                
                print(f"\nSIMULADO (Pessimista + Sazonalidade):")
                print(f"  Receita: R$ {simulated.get('total_receita', 0):,.2f}")
                print(f"  Custo: R$ {simulated.get('total_custo', 0):,.2f}")
                print(f"  Fluxo: R$ {simulated.get('total_fluxo_de_caixa', 0):,.2f}")
                
                # Calcular mudanças percentuais
                receita_change = ((simulated.get('total_receita', 0) - original.get('total_receita', 0)) / original.get('total_receita', 1)) * 100
                fluxo_change = ((simulated.get('total_fluxo_de_caixa', 0) - original.get('total_fluxo_de_caixa', 0)) / original.get('total_fluxo_de_caixa', 1)) * 100
                
                print(f"\nMUDANÇAS:")
                print(f"  Receita: {receita_change:+.1f}%")
                print(f"  Fluxo: {fluxo_change:+.1f}%")
                
            except json.JSONDecodeError as e:
                print(f"❌ Erro ao decodificar JSON: {e}")
                print(f"Resposta recebida: {response.text[:500]}...")
                return False
                
        else:
            print(f"❌ Erro na simulação com sazonalidade")
            print(f"Resposta: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Erro inesperado na simulação com sazonalidade: {e}")
        return False
    
    # Teste 4: Teste de validação (cenário inválido)
    print("\n4. Testando validação (cenário inválido)...")
    
    payload_invalid = {
        "scenario_type": "super_otimista",  # Cenário inválido
        "seasonality_rules": None
    }
    
    try:
        response = requests.post(
            f"{base_url}/api/simulations/scenario-simulation",
            json=payload_invalid,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 400:
            print("✅ Validação funcionando corretamente (retornou erro 400)")
            error_detail = response.json().get('detail', 'Sem detalhes')
            print(f"Erro: {error_detail}")
        else:
            print(f"⚠️  Esperado erro 400, mas recebeu {response.status_code}")
            
    except Exception as e:
        print(f"❌ Erro inesperado no teste de validação: {e}")
    
    print("\n" + "="*60)
    print("TESTES CONCLUÍDOS")
    print("="*60)
    
    return True

def test_with_curl_commands():
    """Mostra comandos curl para testar manualmente."""
    
    print("\n" + "="*60)
    print("COMANDOS CURL PARA TESTE MANUAL")
    print("="*60)
    
    print("\n1. Testar status:")
    print("curl -X GET http://127.0.0.1:8000/api/simulations/status")
    
    print("\n2. Testar simulação básica:")
    print('''curl -X POST http://127.0.0.1:8000/api/simulations/scenario-simulation \\
  -H "Content-Type: application/json" \\
  -d '{
    "scenario_type": "otimista",
    "seasonality_rules": null
  }'
''')
    
    print("\n3. Testar simulação com sazonalidade:")
    print('''curl -X POST http://127.0.0.1:8000/api/simulations/scenario-simulation \\
  -H "Content-Type: application/json" \\
  -d '{
    "scenario_type": "pessimista",
    "seasonality_rules": [
      {
        "month": "Dezembro",
        "revenue_change_percentage": 30
      },
      {
        "month": "Janeiro", 
        "revenue_change_percentage": -20
      }
    ]
  }'
''')

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--curl":
        test_with_curl_commands()
    else:
        success = test_simulation_api()
        if not success:
            print("\n⚠️  Alguns testes falharam. Verifique o servidor e tente novamente.")
            test_with_curl_commands()
        else:
            print("\n✅ Todos os testes passaram com sucesso!")