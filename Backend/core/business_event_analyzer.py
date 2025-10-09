# Backend/core/business_event_analyzer.py

import pandas as pd

def identify_key_business_events(df: pd.DataFrame, top_n: int = 5):
    """
    Analisa o DataFrame de fluxo de caixa para identificar os principais
    clientes (entradas) e custos (saídas) com base na frequência e no volume.
    
    Para entradas, usa produto_normalizado para agrupar produtos iguais com quantidades diferentes.
    Para saídas, continua usando descricao original.
    """
    if df is None or df.empty:
        return {"key_inflows": [], "key_outflows": []}

    # Analisar Entradas (Produtos Chave) - usa produto_normalizado se disponível
    inflows = df[df['entrada'] > 0].copy()
    
    # Verifica se tem a coluna produto_normalizado (dados processados com nova funcionalidade)
    if 'produto_normalizado' in inflows.columns:
        # Usa produto_normalizado para agrupar produtos iguais com quantidades diferentes
        group_col = 'produto_normalizado'
        # Adiciona quantidade total se disponível
        if 'quantidade' in inflows.columns:
            key_inflows = (
                inflows.groupby(group_col).agg({
                    'entrada': ['sum', 'count'],
                    'quantidade': 'sum',
                    'categoria': 'first'
                })
                .sort_values(by=('entrada', 'sum'), ascending=False)
                .head(top_n)
                .reset_index()
            )
            # Renomear colunas para clareza
            key_inflows.columns = ['name', 'total_amount', 'frequency', 'total_quantity', 'category']
            key_inflows = key_inflows[['name', 'total_amount', 'frequency', 'total_quantity', 'category']]
        else:
            key_inflows = (
                inflows.groupby(group_col).agg({
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
    else:
        # Fallback para dados antigos sem normalização
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

    # Analisar Saídas (Custos Chave) - continua usando descricao original
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