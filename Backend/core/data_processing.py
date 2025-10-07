import pandas as pd
import numpy as np
import re
import json
import os

def carregar_regras_de_categorizacao():
    """
    Lê o arquivo regras.json e o carrega em um dicionário Python.
    """
    caminho_arquivo = os.path.join(os.path.dirname(__file__), 'regras.json')
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            print("Carregando regras de categorização do arquivo regras.json...")
            regras = json.load(f)
            return regras
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"ERRO ao carregar regras.json: {e}. A categorização usará um conjunto vazio de regras.")
        return {}

REGRAS_DE_CATEGORIZACAO = carregar_regras_de_categorizacao()

def categorizar_por_regras(descricao):
    """
    Categoriza a transação com base nas regras, com validação de tipo
    para evitar erros com dados mal formatados.
    """
    # Garante 100% que o dado é um texto antes de processar.
    if not isinstance(descricao, str):
        return 'outros'
    
    desc_lower = descricao.lower()

    for categoria, palavras_chave in REGRAS_DE_CATEGORIZACAO.items():
        for palavra in palavras_chave:
            # Garante que a palavra-chave também seja texto
            if isinstance(palavra, str) and palavra in desc_lower:
                return categoria
    
    return 'outros'

def processar_dados(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.str.lower().str.replace(' ', '_')

    df['data'] = pd.to_datetime(df['data'], errors='coerce')
    df.dropna(subset=['data'], inplace=True)
    def normalizar_valores_monetarios(serie):
        serie_str = serie.astype(str)
        # Remove moeda, espaços e qualquer caractere que não seja dígito, vírgula, ponto ou sinal
        serie_str = serie_str.str.replace(r'[^0-9,.-]', '', regex=True)
        # Heurística: se tiver ponto e vírgula, ponto é milhar e vírgula é decimal
        tem_ponto = serie_str.str.contains('\.', regex=False)
        tem_virgula = serie_str.str.contains(',', regex=False)
        ambos = tem_ponto & tem_virgula
        serie_str = serie_str.where(~ambos, serie_str.str.replace('.', '', regex=False))
        serie_str = serie_str.where(~ambos, serie_str.str.replace(',', '.', regex=False))
        # Apenas vírgula -> decimal brasileiro
        somente_virgula = ~tem_ponto & tem_virgula
        serie_str = serie_str.where(~somente_virgula, serie_str.str.replace(',', '.', regex=False))
        # Demais casos mantêm como está
        return pd.to_numeric(serie_str, errors='coerce').fillna(0)

    for col in ['entrada', 'saida']:
        if col in df.columns:
            df[col] = normalizar_valores_monetarios(df[col])
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
    # Ela converte valores vazios (NaN) ou numéricos para texto antes de categorizar.
    df['descricao'] = df['descricao'].astype(str).fillna('')
    
    df['categoria'] = df['descricao'].apply(categorizar_por_regras)

    return df