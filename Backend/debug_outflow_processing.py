# debug_outflow_processing.py
# Debug específico para o processamento de arquivos de saída

import pandas as pd
import sys
import os

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from core.data_processing import process_outflow_file

def debug_outflow_processing():
    """Debug específico para o processamento de arquivos de saída."""
    print("="*80)
    print("DEBUG: PROCESSAMENTO DE ARQUIVOS DE SAÍDA")
    print("="*80)
    
    # Simula exatamente a estrutura das planilhas reais
    test_data = {
        'data': ['2024-01-01', '2024-01-01', '2024-01-01', '2024-01-01', '2024-01-01'],
        'saida': ['Obramax', 'Obramax', 'Eletroleste', 'Obramax', 'Cimeprimo'],  # Nomes dos fornecedores
        'valor': [714.00, 242.40, 556.62, 1307.28, 656.82],  # Valores monetários
        'categoria': ['Fornecedor', 'Fornecedor', 'Fornecedor', 'Fornecedor', 'Fornecedor']
    }
    
    df_raw = pd.DataFrame(test_data)
    df_raw['data'] = pd.to_datetime(df_raw['data'])
    
    print("Dados brutos (antes do processamento):")
    print(df_raw.to_string())
    print()
    
    # Processa o arquivo
    print("Processando arquivo...")
    df_processed = process_outflow_file(df_raw)
    
    print("Dados processados:")
    print(df_processed.to_string())
    print()
    
    print("Estrutura dos dados processados:")
    print(f"Colunas: {list(df_processed.columns)}")
    print(f"Tipos: {df_processed.dtypes.to_dict()}")
    print()
    
    # Testa a função pick_outflow_name com os dados processados
    print("Testando pick_outflow_name com dados processados:")
    
    def pick_outflow_name(row):
        import re
        
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
    
    for idx, row in df_processed.iterrows():
        nome = pick_outflow_name(row)
        print(f"  Linha {idx}: {nome}")
    
    return df_processed

def main():
    """Executa o debug."""
    try:
        df_processed = debug_outflow_processing()
        
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