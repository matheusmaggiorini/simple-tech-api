# Backend/core/business_event_analyzer.py

import pandas as pd

def identify_key_business_events(df: pd.DataFrame, top_n: int = 5):
    """
    Analisa o DataFrame de fluxo de caixa para identificar os principais
    clientes (entradas) e custos (saídas) com base na frequência e no volume.
    """
    if df is None or df.empty:
        return {"key_inflows": [], "key_outflows": []}

    # Analisar Entradas (Clientes/Produtos Chave)
    inflows = df[df['entrada'] > 0].copy()
    key_inflows = (
        inflows.groupby('descricao').agg({
            'entrada': ['sum', 'count'],
            'categoria': 'first'
        })
        .sort_values(by=('entrada', 'sum'), ascending=False)
        .head(top_n)
        .reset_index()
    )
    # Renomear colunas para clareza
    key_inflows.columns = ['name', 'total_amount', 'frequency', 'category']
    key_inflows = key_inflows[['name', 'total_amount', 'frequency', 'category']]


    # Analisar Saídas (Custos Chave)
    outflows = df[df['saida'] > 0].copy()
    key_outflows = (
        outflows.groupby('descricao').agg({
            'saida': ['sum', 'count'],
            'categoria': 'first'
        })
        .sort_values(by=('saida', 'sum'), ascending=False)
        .head(top_n)
        .reset_index()
    )
    # Renomear colunas para clareza
    key_outflows.columns = ['name', 'total_amount', 'frequency', 'category']
    key_outflows = key_outflows[['name', 'total_amount', 'frequency', 'category']]


    return {
        "key_inflows": key_inflows.to_dict(orient='records'),
        "key_outflows": key_outflows.to_dict(orient='records')
    }