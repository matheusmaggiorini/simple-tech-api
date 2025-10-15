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
    
    # Remove "FRETE + TAXAS" das receitas pois não é um produto real
    if 'descricao' in inflows.columns:
        inflows = inflows[~inflows['descricao'].str.contains(r'FRETE \+ TAXAS', case=False, na=False)]

    # Constrói um dataframe expandido SOMENTE para análise (não altera o original):
    expanded_rows = []
    
    # Primeiro, constrói um mapa de preços unitários conhecidos a partir de transações de item único
    precos_unitarios_por_produto = {}
    for _, row in inflows.iterrows():
        valor_total = float(row.get('entrada', 0) or 0)
        desc = row.get('descricao', '')
        itens = _split_inflow_description_with_quantities(desc)
        
        # Se é um item único, calcula o preço unitário
        if len(itens) == 1:
            qtd, produto = itens[0]
            if qtd > 0 and produto:
                preco_unitario = valor_total / qtd
                if produto not in precos_unitarios_por_produto:
                    precos_unitarios_por_produto[produto] = []
                precos_unitarios_por_produto[produto].append(preco_unitario)
    
    # Calcula preços médios para produtos com múltiplas transações
    for produto in precos_unitarios_por_produto:
        if len(precos_unitarios_por_produto[produto]) > 1:
            precos_unitarios_por_produto[produto] = [sum(precos_unitarios_por_produto[produto]) / len(precos_unitarios_por_produto[produto])]
        else:
            precos_unitarios_por_produto[produto] = precos_unitarios_por_produto[produto]
    
    # Converte para formato esperado pela função processar_descricao_multiplos_produtos
    precos_map = {produto: precos[0] for produto, precos in precos_unitarios_por_produto.items()}
    
    # Agora processa todas as transações usando a lógica melhorada
    for _, row in inflows.iterrows():
        valor_total = float(row.get('entrada', 0) or 0)
        desc = row.get('descricao', '')
        
        # Usa a função melhorada para processar descrições com múltiplos produtos
        from .data_processing import processar_descricao_multiplos_produtos
        itens_processados = processar_descricao_multiplos_produtos(desc, valor_total, precos_map)
        
        for qtd, produto, valor_item in itens_processados:
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
        # Prioriza a coluna SAIDA (nome do fornecedor) se disponível
        if 'saida' in row.index:
            val = row['saida']
            if pd.notna(val):
                text = str(val).strip()
                # Se não é numérico e não está vazio, é provavelmente o nome do fornecedor
                if text and not re.fullmatch(r"[-+]?\d+(?:[.,]\d+)?", text) and text.lower() not in ['nan', 'none', '']:
                    return text
        
        # Se SAIDA não está disponível ou é numérica, tenta outras colunas textuais
        for col in ['fornecedor', 'forma', 'descricao', 'tipo']:
            if col in row.index:
                val = row[col]
                if pd.isna(val):
                    continue
                text = str(val).strip()
                if not text or text.lower() in ['nan', 'none']:
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