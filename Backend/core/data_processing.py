import pandas as pd
import numpy as np
import re
import json # Importa a biblioteca para ler o arquivo JSON
import os   # Importa a biblioteca para lidar com caminhos de arquivo

# ==============================================================================
# ==== CARREGAMENTO DINÂMICO DAS REGRAS DE CATEGORIZAÇÃO ====
# ==============================================================================

def carregar_regras_de_categorizacao():
    """
    Lê o arquivo regras.json e o carrega em um dicionário Python.
    Isso permite que as regras sejam editadas sem alterar o código.
    """
    # Constrói o caminho para o arquivo de regras, garantindo que funcione em qualquer sistema
    caminho_arquivo = os.path.join(os.path.dirname(__file__), 'regras.json')
    
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            print("Carregando regras de categorização do arquivo regras.json...")
            regras = json.load(f)
            return regras
    except FileNotFoundError:
        print(f"ERRO: Arquivo de regras '{caminho_arquivo}' não encontrado. A categorização usará um conjunto vazio de regras.")
        return {}
    except json.JSONDecodeError:
        print(f"ERRO: O arquivo de regras '{caminho_arquivo}' não é um JSON válido.")
        return {}

# Carrega as regras uma vez quando o módulo é iniciado
REGRAS_DE_CATEGORIZACAO = carregar_regras_de_categorizacao()

# --- O restante do código permanece o mesmo, mas agora usa as regras carregadas ---

def categorizar_por_regras(descricao):
    """
    Categoriza a transação com base no dicionário de regras carregado do arquivo JSON.
    """
    desc_lower = str(descricao).lower()

    for categoria, palavras_chave in REGRAS_DE_CATEGORIZACAO.items():
        for palavra in palavras_chave:
            if palavra in desc_lower:
                return categoria
    
    return 'outros'

def processar_dados(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.str.lower().str.replace(' ', '_')

    df['data'] = pd.to_datetime(df['data'], errors='coerce')
    df.dropna(subset=['data'], inplace=True)
    for col in ['entrada', 'saida']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).replace(',', '.', regex=False), errors='coerce').fillna(0)
    if 'entrada' not in df.columns: df['entrada'] = 0
    if 'saida' not in df.columns: df['saida'] = 0

    df.sort_values(by='data', inplace=True)
    df.reset_index(drop=True, inplace=True)

    df['fluxo_diario'] = df['entrada'] - df['saida']
    df['saldo'] = df['fluxo_diario'].cumsum()
    
    df['ano'] = df['data'].dt.year
    df['mes'] = df['data'].dt.month
    df['dia'] = df['data'].dt.day
    df['dia_da_semana'] = df['data'].dt.dayofweek
    df['semana_do_ano'] = df['data'].dt.isocalendar().week.astype(int)
    
    df['categoria'] = df['descricao'].apply(categorizar_por_regras)

    return df