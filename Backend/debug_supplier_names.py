# debug_supplier_names.py
# Debug específico para investigar o problema dos nomes de fornecedores

import pandas as pd
import sys
import os
import re

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from core.business_event_analyzer import identify_key_business_events

def debug_supplier_processing():
    """Debug específico para o processamento de fornecedores."""
    print("="*80)
    print("DEBUG: PROCESSAMENTO DE FORNECEDORES")
    print("="*80)
    
    # Simula exatamente a estrutura das planilhas reais
    test_data = {
        'data': ['2024-01-01', '2024-01-01', '2024-01-01', '2024-01-01', '2024-01-01'],
        'saida': [714.00, 242.40, 556.62, 1307.28, 656.82],  # Valores monetários
        'entrada': [0, 0, 0, 0, 0],
        'descricao': ['Obramax', 'Obramax', 'Eletroleste', 'Obramax', 'Cimeprimo'],  # Nomes dos fornecedores
        'categoria': ['Fornecedor', 'Fornecedor', 'Fornecedor', 'Fornecedor', 'Fornecedor']
    }
    
    df = pd.DataFrame(test_data)
    df['data'] = pd.to_datetime(df['data'])
    
    print("Dados de entrada:")
    print(df.to_string())
    print()
    
    # Testa a função pick_outflow_name diretamente
    print("Testando função pick_outflow_name:")
    
    def pick_outflow_name(row):
        # Prioriza a coluna SAIDA (nome do fornecedor) se disponível
        if 'saida' in row.index:
            val = row['saida']
            if pd.notna(val):
                text = str(val).strip()
                if text and not re.fullmatch(r"[-+]?\d+(?:[.,]\d+)?", text):
                    return text
        
        # Se SAIDA não está disponível ou é numérica, tenta outras colunas textuais
        for col in ['fornecedor', 'forma', 'descricao', 'tipo']:
            if col in row.index:
                val = row[col]
                if pd.isna(val):
                    continue
                text = str(val).strip()
                if not text:
                    continue
                # Ignora strings puramente numéricas
                if re.fullmatch(r"[-+]?\d+(?:[.,]\d+)?", text):
                    continue
                return text
        
        # Se não encontrou descrição textual, usa valores numéricos como último recurso
        for col in ['valor', 'valor_total']:
            if col in row.index:
                val = row[col]
                if pd.isna(val):
                    continue
                text = str(val).strip()
                if not text:
                    continue
                # Se é numérico, usa como identificador com prefixo
                if re.fullmatch(r"[-+]?\d+(?:[.,]\d+)?", text):
                    return f"Custo #{text}"
                return text
        
        return 'Desconhecido'
    
    print("Testando pick_outflow_name para cada linha:")
    for idx, row in df.iterrows():
        nome = pick_outflow_name(row)
        print(f"  Linha {idx}: {nome}")
    print()
    
    # Executa a análise completa
    print("Executando análise completa...")
    result = identify_key_business_events(df, top_n=5)
    
    print("Resultado da análise:")
    print("Custos identificados:")
    for outflow in result['key_outflows']:
        print(f"  {outflow['name']}: R$ {outflow['total_amount']:.2f}")
    
    return result

def debug_real_data_structure():
    """Debug com a estrutura real dos dados."""
    print("="*80)
    print("DEBUG: ESTRUTURA REAL DOS DADOS")
    print("="*80)
    
    # Simula a estrutura exata das planilhas de saída
    test_data = {
        'data': ['2024-01-01', '2024-01-01', '2024-01-01', '2024-01-01', '2024-01-01'],
        'saida': [714.00, 242.40, 556.62, 1307.28, 656.82],  # Esta é a coluna de VALORES
        'entrada': [0, 0, 0, 0, 0],
        'descricao': ['Obramax', 'Obramax', 'Eletroleste', 'Obramax', 'Cimeprimo'],  # Esta é a coluna SAIDA (fornecedores)
        'categoria': ['Fornecedor', 'Fornecedor', 'Fornecedor', 'Fornecedor', 'Fornecedor']
    }
    
    df = pd.DataFrame(test_data)
    df['data'] = pd.to_datetime(df['data'])
    
    print("Estrutura dos dados:")
    print(f"Colunas: {list(df.columns)}")
    print(f"Tipos: {df.dtypes.to_dict()}")
    print()
    
    print("Dados:")
    print(df.to_string())
    print()
    
    # Testa a função pick_outflow_name com a estrutura real
    def pick_outflow_name_debug(row):
        print(f"Processando linha: {row.to_dict()}")
        
        # Prioriza a coluna SAIDA (nome do fornecedor) se disponível
        if 'saida' in row.index:
            val = row['saida']
            print(f"  Coluna 'saida' encontrada: {val} (tipo: {type(val)})")
            if pd.notna(val):
                text = str(val).strip()
                print(f"  Texto: '{text}'")
                if text and not re.fullmatch(r"[-+]?\d+(?:[.,]\d+)?", text):
                    print(f"  Retornando: {text}")
                    return text
                else:
                    print(f"  É numérico, ignorando")
        
        # Se SAIDA não está disponível ou é numérica, tenta outras colunas textuais
        for col in ['fornecedor', 'forma', 'descricao', 'tipo']:
            if col in row.index:
                val = row[col]
                print(f"  Tentando coluna '{col}': {val}")
                if pd.isna(val):
                    continue
                text = str(val).strip()
                if not text:
                    continue
                # Ignora strings puramente numéricas
                if re.fullmatch(r"[-+]?\d+(?:[.,]\d+)?", text):
                    continue
                print(f"  Retornando: {text}")
                return text
        
        print(f"  Retornando: Desconhecido")
        return 'Desconhecido'
    
    print("Testando pick_outflow_name com debug:")
    for idx, row in df.iterrows():
        print(f"\n--- Linha {idx} ---")
        nome = pick_outflow_name_debug(row)
        print(f"Resultado: {nome}")

def main():
    """Executa o debug."""
    try:
        # Debug 1: Processamento básico
        result1 = debug_supplier_processing()
        
        # Debug 2: Estrutura real
        debug_real_data_structure()
        
        print("="*80)
        print("DEBUG CONCLUÍDO")
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
        print("\n✅ Debug concluído!")