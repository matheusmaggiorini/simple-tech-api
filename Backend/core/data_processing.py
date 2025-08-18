import pandas as pd
import numpy as np
import re

# ==============================================================================
# ==== SISTEMA DE REGRAS PARA CATEGORIZAÇÃO ====
# ==============================================================================
REGRAS_DE_CATEGORIZACAO = {
    'receitas': [
        'salario', 'salário', 'adiantamento', 'bonus', 'bônus', 'vencimento',
        'recebimento', 'venda', 'consultoria', 'freelance', 'aluguel recebido',
        'restituicao', '13o'
    ],
    'transporte': [
        'uber', '99', 'taxi', 'gasolina', 'combustivel', 'estacionamento',
        'bilhete unico', 'onibus', 'ônibus', 'carro', 'ipva', 'seguro do veiculo', 'pedagio'
    ],
    'moradia': [
        'aluguel', 'condominio', 'condomínio', 'conta de luz', 'enel', 'iptu',
        'conta de agua', 'internet', 'tv a cabo', 'gas', 'gás', 'diarista', 'reforma'
    ],
    'pessoal_e_saude': [
        'farmacia', 'farmácia', 'remedio', 'remédio', 'medico', 'médico', 'consulta',
        'plano de saude', 'exame', 'dentista', 'academia', 'corte de cabelo',
        'roupas', 'perfume'
    ],
    'lazer_e_educacao': [
        'restaurante', 'ifood', 'bar', 'cinema', 'show', 'viagem', 'livro',
        'netflix', 'spotify', 'jogo', 'game', 'faculdade', 'curso', 'escola', 'palestra'
    ],
    'financeiro': [
        'fatura', 'cartao de credito', 'cartão', 'emprestimo', 'empréstimo', 'tarifa',
        'boleto', 'imposto', 'taxa', 'pix', 'transferencia', 'investimento', 'acoes'
    ],
    'compras_online': [
        'amazon', 'mercado livre', 'aliexpress', 'shopee', 'loja online', 'software'
    ],
    'alimentacao': [
        'mercado', 'supermercado', 'hortifruti', 'padaria', 'lanche', 'almoco', 'almoço',
        'jantar', 'pizza', 'acai', 'açaí'
    ]
}

def categorizar_por_regras(descricao):
    """
    Categoriza a transação com base no dicionário de regras.
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
    
    # --- A CORREÇÃO ESTÁ AQUI ---
    # Renomeando 'saldo_acumulado' para 'saldo'
    df['saldo'] = df['fluxo_diario'].cumsum()
    
    df['ano'] = df['data'].dt.year
    df['mes'] = df['data'].dt.month
    df['dia'] = df['data'].dt.day
    df['dia_da_semana'] = df['data'].dt.dayofweek
    df['semana_do_ano'] = df['data'].dt.isocalendar().week.astype(int)
    
    df['categoria'] = df['descricao'].apply(categorizar_por_regras)

    return df