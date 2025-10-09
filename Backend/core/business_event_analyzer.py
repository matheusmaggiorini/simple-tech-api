# Backend/core/business_event_analyzer.py

import pandas as pd
import re

def _split_inflow_description_with_quantities(descricao: str):
    """Divide descrições de entradas que podem conter múltiplos itens no formato
    "N X PRODUTO" por linha. Retorna lista de tuplas (quantidade, produto).
    Não altera valores; apenas informa quantidades e nomes.
    """
    if not isinstance(descricao, str) or not descricao.strip():
        return [(1.0, '')]
    linhas = [l.strip() for l in descricao.split('\n') if l.strip()]
    if not linhas:
        linhas = [descricao.strip()]

    itens = []
    pattern = re.compile(r"^(\d+(?:[.,]\d+)?)\s*[xX]\s+(.+)$")
    for linha in linhas:
        m = pattern.match(linha)
        if m:
            qtd = float(m.group(1).replace(',', '.'))
            prod = m.group(2).strip()
            itens.append((qtd if qtd > 0 else 1.0, prod))
        else:
            itens.append((1.0, linha))
    return itens


def identify_key_business_events(df: pd.DataFrame, top_n: int = 5):
    """
    Analisa o DataFrame de fluxo de caixa para identificar os principais
    clientes (entradas) e custos (saídas) com base na frequência e no volume.

    Para entradas, interpreta "N X PRODUTO" dentro da descrição.
    Para saídas, tenta identificar fornecedor/forma/tipo como nome do custo.
    """
    if df is None or df.empty:
        return {"key_inflows": [], "key_outflows": []}

    # Analisar Entradas (Produtos Chave) - interpretar descrições com quantidades
    inflows = df[df['entrada'] > 0].copy()

    # Constrói um dataframe expandido SOMENTE para análise (não altera o original):
    expanded_rows = []
    for _, row in inflows.iterrows():
        valor_total = float(row.get('entrada', 0) or 0)
        desc = row.get('descricao', '')
        itens = _split_inflow_description_with_quantities(desc)
        quantidade_total = sum(q for q, _ in itens) or 1.0
        # Valor proporcional por item com base na quantidade
        for qtd, produto in itens:
            valor_item = valor_total * (qtd / quantidade_total)
            expanded_rows.append({
                'produto': produto,
                'valor': valor_item,
                'quantidade': qtd,
                'categoria': row.get('categoria', '')
            })

    if expanded_rows:
        inflow_expanded = pd.DataFrame(expanded_rows)
        key_inflows = (
            inflow_expanded.groupby('produto').agg({
                'valor': ['sum', 'count'],
                'quantidade': 'sum',
                'categoria': 'first'
            })
            .sort_values(by=('valor', 'sum'), ascending=False)
            .head(top_n)
            .reset_index()
        )
        key_inflows.columns = ['name', 'total_amount', 'frequency', 'total_quantity', 'category']
        key_inflows = key_inflows[['name', 'total_amount', 'frequency', 'total_quantity', 'category']]
    else:
        key_inflows = pd.DataFrame(columns=['name', 'total_amount', 'frequency', 'total_quantity', 'category'])

    # Analisar Saídas (Custos Chave) - robusto por fornecedor/origem
    outflows = df[df['saida'] > 0].copy()

    # Construir melhor nome do custo
    def pick_outflow_name(row):
        for col in ['fornecedor', 'forma', 'descricao', 'saida', 'tipo']:
            if col in row.index:
                val = row[col]
                if pd.isna(val):
                    continue
                text = str(val).strip()
                if not text:
                    continue
                # Ignora strings numéricas
                if re.fullmatch(r"[-+]?\d+(?:[.,]\d+)?", text):
                    continue
                return text
        return 'Desconhecido'

    outflows['__nome_custo'] = outflows.apply(pick_outflow_name, axis=1)
    outflows['__nome_custo'] = outflows['__nome_custo'].replace({'nan': 'Desconhecido', 'None': 'Desconhecido'}).fillna('Desconhecido')

    key_outflows = (
        outflows.groupby('__nome_custo').agg({
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