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

def extrair_quantidade_e_produto(descricao):
    """
    Extrai quantidade e normaliza o nome do produto de uma descrição.
    
    Exemplos:
    - "2 X RATICIDA KROMAX" -> (2, "RATICIDA KROMAX")
    - "1 X PORTA SANFONADA" -> (1, "PORTA SANFONADA")
    - "PRODUTO SEM QUANTIDADE" -> (1, "PRODUTO SEM QUANTIDADE")
    
    Retorna: (quantidade, produto_normalizado)
    """
    if not isinstance(descricao, str) or not descricao.strip():
        return 1, descricao
    
    descricao = descricao.strip()
    
    # Padrão: número + X + produto (ex: "2 X RATICIDA KROMAX")
    import re
    pattern = r'^(\d+(?:[.,]\d+)?)\s*[xX]\s+(.+)$'
    match = re.match(pattern, descricao)
    
    if match:
        quantidade_str = match.group(1).replace(',', '.')
        produto = match.group(2).strip()
        
        try:
            quantidade = float(quantidade_str)
            return quantidade, produto
        except ValueError:
            return 1, descricao
    
    # Se não encontrou o padrão, assume quantidade 1
    return 1, descricao

def processar_descricao_multiplos_produtos(descricao, valor_total, precos_unitarios_por_produto=None):
    """
    Processa uma descrição que pode conter múltiplos produtos separados por quebras de linha.
    
    Exemplo:
    "10 X SANLIMP 5LT\n10 X ALCOOL 70% 1L\n10 X DESINFETANTE FLO"
    
    Retorna: Lista de tuplas (quantidade, produto, valor_alocado)
    """
    if not isinstance(descricao, str) or not descricao.strip():
        return [(1, descricao, valor_total)]
    
    # Divide por quebras de linha
    linhas = [linha.strip() for linha in descricao.split('\n') if linha.strip()]
    
    if len(linhas) <= 1:
        # Se tem apenas uma linha, processa normalmente
        quantidade, produto = extrair_quantidade_e_produto(descricao)
        # Se houver preço unitário conhecido, usa-o, senão atribui tudo ao item
        if isinstance(precos_unitarios_por_produto, dict):
            preco_unit = precos_unitarios_por_produto.get(produto)
            if preco_unit is not None and quantidade is not None and quantidade > 0:
                valor = preco_unit * quantidade
                return [(quantidade, produto, valor)]
        return [(quantidade, produto, valor_total)]
    
    # Se tem múltiplas linhas, processa cada uma
    produtos = []
    total_quantidade = 0
    
    for linha in linhas:
        quantidade, produto = extrair_quantidade_e_produto(linha)
        produtos.append((quantidade, produto))
        total_quantidade += quantidade
    
    # Se total_quantidade for 0, assume 1 para cada produto
    if total_quantidade == 0:
        total_quantidade = len(produtos)
        produtos = [(1, produto) for _, produto in produtos]
    
    # Se houver mapa de preços unitários, alocar primeiro itens com preço conhecido
    resultado = []
    valor_conhecido_total = 0.0
    itens_desconhecidos = []
    precos_map = precos_unitarios_por_produto if isinstance(precos_unitarios_por_produto, dict) else {}
    
    for quantidade, produto in produtos:
        preco_unit = precos_map.get(produto)
        if preco_unit is not None and quantidade > 0:
            valor_item = preco_unit * quantidade
            resultado.append((quantidade, produto, valor_item))
            valor_conhecido_total += valor_item
        else:
            itens_desconhecidos.append((quantidade, produto))

    # Calcula o restante a ser distribuído
    restante = valor_total - valor_conhecido_total
    if restante < 0:
        # Se preços conhecidos excedem o total (inconsistência), não permitir negativo
        restante = 0.0

    # Distribui o restante proporcional à quantidade total dos itens sem preço
    if itens_desconhecidos:
        qtd_desconhecida_total = sum(q for q, _ in itens_desconhecidos if q is not None)
        if qtd_desconhecida_total and qtd_desconhecida_total > 0:
            valor_unit_desconhecido = restante / qtd_desconhecida_total
            for quantidade, produto in itens_desconhecidos:
                valor_item = valor_unit_desconhecido * quantidade
                resultado.append((quantidade, produto, valor_item))
        else:
            # Fallback: dividir igualmente entre os itens desconhecidos
            valor_por_item = restante / len(itens_desconhecidos)
            for quantidade, produto in itens_desconhecidos:
                resultado.append((quantidade, produto, valor_por_item))
    
    # Se não havia mapa de preços, ou nenhum preço conhecido encontrado, distribuir por quantidade
    if not isinstance(precos_unitarios_por_produto, dict) or not resultado:
        resultado = []
        for quantidade, produto in produtos:
            valor_proporcional = (quantidade / total_quantidade) * valor_total
            resultado.append((quantidade, produto, valor_proporcional))

    return resultado

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

def processar_dados(df: pd.DataFrame, filename: str = None) -> pd.DataFrame:
    df.columns = df.columns.str.lower().str.replace(' ', '_')

    # Detecta formato específico de planilha de ENTRADAS (Exportar) e pré-processa
    has_valor_pago_col = any(c in df.columns for c in ['valor_pago', 'valor\u00a0pago', 'valor_pago_(r$)'])
    has_numeric_excel_date = 'data' in df.columns and (
        pd.api.types.is_integer_dtype(df['data']) or pd.api.types.is_float_dtype(df['data'])
    )
    # Detecta arquivos de entrada por nome também
    is_inflow_by_name = filename and any(keyword in filename.lower() for keyword in ['entrada', 'entradas', 'receita', 'receitas', 'venda', 'vendas'])
    
    if has_valor_pago_col or has_numeric_excel_date or is_inflow_by_name:
        try:
            print(f"[DEBUG] Processando como arquivo de ENTRADA: {filename}")
            df = process_inflow_file(df)
        except Exception as e:
            print(f"[DEBUG] Erro ao processar como entrada: {e}")
            # Se falhar, segue o fluxo genérico
            pass
    
    # Heurística melhorada para arquivos de SAÍDA
    # Detecta por nome do arquivo (ex: "Cópia de 02 - Fevereiro.csv") ou estrutura
    is_outflow_by_name = filename and any(keyword in filename.lower() for keyword in ['saida', 'saída', 'fevereiro', 'janeiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro', 'cópia', 'yuuuecnbiosksnud'])
    
    has_data_and_valor = ('data' in df.columns) and any('valor' == c for c in df.columns)
    duplicate_valor_cols = [c for c in df.columns if c == 'valor']
    has_saida_col = 'saida' in df.columns
    
    # Detecta arquivo de saída por estrutura ou nome
    is_outflow_by_structure = (has_data_and_valor and len(duplicate_valor_cols) >= 1 and 
                              'entrada' not in df.columns and not has_saida_col)
    
    # Detecta estrutura específica da planilha de saídas (SAIDA, VALOR, Data)
    is_outflow_specific_structure = (has_data_and_valor and 'saida' in df.columns and 
                                   df.columns.tolist() == ['saida', 'valor', 'data'])
    
    if is_outflow_by_name or is_outflow_by_structure or is_outflow_specific_structure:
        try:
            print(f"[DEBUG] Processando como arquivo de SAÍDA: {filename}")
            df = process_outflow_file(df)
            # Se o arquivo está vazio após processamento, não é um erro
            if df.empty:
                print(f"[DEBUG] Arquivo {filename} está vazio - continuando processamento")
        except Exception as e:
            print(f"[DEBUG] Erro ao processar como saída: {e}")
            # Se é um arquivo vazio, criar DataFrame vazio em vez de falhar
            if "não contém dados válidos" in str(e).lower():
                df = pd.DataFrame(columns=['data', 'saida', 'descricao', 'entrada'])
                print(f"[DEBUG] Criando DataFrame vazio para {filename}")
            else:
                pass

    # Fallbacks para localizar colunas essenciais que possam ter nomes diferentes
    if 'data' not in df.columns:
        possiveis_datas = [c for c in df.columns if c in ['date', 'dt', 'data_mov', 'data_lancamento']]
        if possiveis_datas:
            df.rename(columns={possiveis_datas[0]: 'data'}, inplace=True)

    if 'descricao' not in df.columns:
        possiveis_desc = [c for c in df.columns if c in ['descrição', 'description', 'historico', 'histórico']]
        if possiveis_desc:
            df.rename(columns={possiveis_desc[0]: 'descricao'}, inplace=True)

    # Tenta mapear entrada/saída a partir de outras denominações comuns
    lower_cols = set(df.columns)
    if 'entrada' not in lower_cols:
        for candidato in ['valor_pago', 'valorpago', 'valor_total', 'total_final', 'valor_recebido', 'credito', 'crédito']:
            if candidato in lower_cols:
                df.rename(columns={candidato: 'entrada'}, inplace=True)
                break
    if 'saida' not in lower_cols:
        for candidato in ['valor_pago_saida', 'valor_total_pago', 'valor_debito', 'débito', 'debito', 'pagamento', 'valor_pago_saidas']:
            if candidato in lower_cols:
                df.rename(columns={candidato: 'saida'}, inplace=True)
                break

    # Datas: suporta números de série do Excel e datas BR
    if pd.api.types.is_integer_dtype(df['data']) or pd.api.types.is_float_dtype(df['data']):
        df['data'] = pd.to_datetime(df['data'], origin='1899-12-30', unit='D', errors='coerce')
    else:
        df['data'] = pd.to_datetime(df['data'], errors='coerce', dayfirst=True)
    df.dropna(subset=['data'], inplace=True)
    def normalizar_valores_monetarios(serie):
        return _normalizar_valores_monetarios_series(serie)

    for col in ['entrada', 'saida']:
        if col in df.columns:
            df[col] = normalizar_valores_monetarios(df[col])
    if 'entrada' not in df.columns: df['entrada'] = 0
    if 'saida' not in df.columns: df['saida'] = 0

    # Não filtrar por cancelamento: manter dados como vieram da planilha

    # Garante que entradas ausentes sejam 0, e remove valores negativos de entrada (apenas entradas)
    if 'entrada' in df.columns:
        df['entrada'] = df['entrada'].fillna(0)
    if 'saida' in df.columns:
        df['saida'] = df['saida'].fillna(0)

    # Reconstrói fluxo e saldo se necessário
    if 'entrada' in df.columns and 'saida' in df.columns:
        df['fluxo_diario'] = df['entrada'] - df['saida']
        df['saldo'] = df['fluxo_diario'].cumsum()

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
    if 'descricao' in df.columns:
        df['descricao'] = df['descricao'].astype(str).fillna('')
        
        # Extrai quantidade e normaliza produto para entradas
        if 'entrada' in df.columns and df['entrada'].sum() > 0:
            # Requisito: não dividir entradas por produtos; manter total exatamente como na planilha
            df['quantidade'] = 1
            df['produto_normalizado'] = df['descricao']
        else:
            # Para saídas, mantém como está
            df['quantidade'] = 1
            df['produto_normalizado'] = df['descricao']
        
        df['categoria'] = df['descricao'].apply(categorizar_por_regras)
    else:
        df['descricao'] = ''
        df['quantidade'] = 1
        df['produto_normalizado'] = ''
        df['categoria'] = 'outros'

    return df


def _normalizar_valores_monetarios_series(serie: pd.Series) -> pd.Series:
    def normalize_single_value(value):
        if pd.isna(value) or value == '' or value == 'nan':
            return 0.0
        
        # Converte para string e remove caracteres não numéricos
        str_val = str(value).replace('R$', '').replace(' ', '').strip()
        str_val = ''.join(c for c in str_val if c.isdigit() or c in '.,-')
        
        if not str_val:
            return 0.0
        
        # Detecta formato brasileiro
        has_comma = ',' in str_val
        has_dot = '.' in str_val
        
        if has_comma and has_dot:
            # Formato: 1.234,56 -> ponto é milhar, vírgula é decimal
            str_val = str_val.replace('.', '').replace(',', '.')
        elif has_comma and not has_dot:
            # Formato: 1234,56 -> vírgula é decimal
            str_val = str_val.replace(',', '.')
        # Se só tem ponto, assume que é decimal (formato americano)
        
        try:
            return float(str_val)
        except:
            return 0.0
    
    return serie.apply(normalize_single_value)


def _converter_coluna_data_excel(col: pd.Series) -> pd.Series:
    if pd.api.types.is_integer_dtype(col) or pd.api.types.is_float_dtype(col):
        return pd.to_datetime(col, origin='1899-12-30', unit='D', errors='coerce')
    
    # Tenta diferentes formatos de data
    parsed = pd.to_datetime(col, errors='coerce', dayfirst=True)
    
    # Se ainda há valores nulos, tenta outros formatos
    if parsed.isna().any():
        # Tenta formato DD/MM
        mask = parsed.isna()
        if mask.any():
            parsed.loc[mask] = pd.to_datetime(col.loc[mask], format='%d/%m', errors='coerce')
        
        # Se ainda há valores nulos, tenta formato DD/MM/YYYY
        mask = parsed.isna()
        if mask.any():
            parsed.loc[mask] = pd.to_datetime(col.loc[mask], format='%d/%m/%Y', errors='coerce')
    
    # Corrigir datas que foram interpretadas como 1900 (formato DD/MM sem ano)
    if not parsed.empty:
        # Se todas as datas estão em 1900, assumir que é o ano atual
        if parsed.dt.year.iloc[0] == 1900 and parsed.dt.year.nunique() == 1:
            current_year = pd.Timestamp.now().year
            parsed = parsed + pd.DateOffset(years=current_year - 1900)
    
    return parsed


def process_inflow_file(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Processa planilhas de ENTRADAS no padrão Exportar (XLS/CSV).
    - Usa coluna 'Valor Pago' como entrada
    - Converte datas numéricas do Excel
    - Remove linhas com Cancelado == Sim
    Retorna DataFrame com colunas: data, descricao, entrada, saida
    """
    df = df_raw.copy()
    df.columns = [str(c).strip() for c in df.columns]
    lower_to_original = {str(c).strip().lower(): c for c in df.columns}

    # Não filtrar cancelados: manter todas as linhas conforme solicitado

    # Data
    data_col = None
    for k in ['data', 'date']:
        if k in lower_to_original:
            data_col = lower_to_original[k]
            break
    if data_col is None:
        raise ValueError("Coluna 'Data' não encontrada.")
    df['data'] = _converter_coluna_data_excel(df[data_col])
    df.dropna(subset=['data'], inplace=True)

    # Descrição
    desc_col = None
    for k in ['descricao', 'descrição', 'description', 'historico', 'histórico']:
        if k in lower_to_original:
            desc_col = lower_to_original[k]
            break
    df['descricao'] = df[desc_col].astype(str).fillna('') if desc_col else ''

    # Valor Pago
    valor_pago_col = None
    for k in ['valor pago', 'valor_pago', 'valor\u00a0pago', 'valor pago (r$)', 'valor pago r$']:
        if k in lower_to_original:
            valor_pago_col = lower_to_original[k]
            break
    if valor_pago_col is None:
        raise ValueError("Coluna 'Valor Pago' não encontrada.")
    df['entrada'] = _normalizar_valores_monetarios_series(df[valor_pago_col])
    df = df[pd.to_numeric(df['entrada'], errors='coerce').fillna(0) > 0].copy()
    df['saida'] = 0.0

    return df


def process_outflow_file(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Processa planilhas de SAÍDAS com estrutura semelhante a
    'Cópia de 01 - Janeiro.csv':
    - Colunas incluem 'DATA' e múltiplas 'VALOR'; a última costuma trazer o valor correto
    - Linha de totais e espaços em branco devem ser descartados
    - Suporta arquivos vazios (retorna DataFrame vazio em vez de erro)
    Retorna DataFrame com colunas padronizadas.
    """
    df = df_raw.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    # Seleciona coluna de data
    if 'data' not in df.columns:
        raise ValueError("Coluna 'DATA' não encontrada para saídas.")
    df['data'] = _converter_coluna_data_excel(df['data'])

    # Descartar linhas de totais ou cabeçalhos repetidos
    def _row_has_total(r):
        return any(isinstance(v, str) and 'total' in v.lower() for v in r.values)
    df = df[~df.apply(_row_has_total, axis=1)].copy()

    # Valor: escolher a última coluna chamada 'valor'
    valor_cols = [c for c in df.columns if c == 'valor']
    if not valor_cols:
        raise ValueError("Coluna 'VALOR' não encontrada para saídas.")
    valor_col = valor_cols[-1]
    
    # Se não foi processado acima, normaliza os valores monetários
    if 'saida' not in df.columns or df['saida'].sum() == 0:
        valores_normalizados = _normalizar_valores_monetarios_series(df[valor_col]).fillna(0)
        df['saida'] = valores_normalizados
        # Remove linhas com valores zerados ou inválidos
        df = df[df['saida'] > 0].copy()

    # Remover linhas inválidas/zeradas e completamente vazias
    df = df.dropna(how='all').copy()
    
    # Verificar se ainda há dados válidos após a limpeza
    if df.empty:
        print("[DEBUG] Arquivo de saída vazio após processamento - retornando DataFrame vazio")
        # Retorna DataFrame vazio com estrutura correta em vez de erro
        empty_df = pd.DataFrame(columns=['data', 'saida', 'descricao', 'entrada'])
        return empty_df

    # Para planilhas de saída, mapeia corretamente as colunas
    if 'saida' in df.columns and 'valor' in df.columns:
        # A coluna SAIDA contém o nome do fornecedor (não é valor monetário)
        df['descricao'] = df['saida'].astype(str).fillna('')
        # A coluna VALOR contém os valores monetários - substitui a coluna saida
        df['saida'] = _normalizar_valores_monetarios_series(df['valor']).fillna(0)
        # Remove linhas com valores zerados
        df = df[df['saida'] > 0].copy()
    else:
        # Fallback para outras estruturas
        desc_col = None
        for cand in ['fornecedor', 'forma', 'descricao', 'tipo']:
            if cand in df.columns and cand != 'valor':
                desc_col = cand
                break
        if desc_col is None:
            try:
                idx = list(df.columns).index(valor_col)
                if idx - 1 >= 0:
                    prev_col = list(df.columns)[idx - 1]
                    if prev_col != 'valor':
                        desc_col = prev_col
            except Exception:
                desc_col = None
        
        # Garante que sempre há uma descrição
        if desc_col and desc_col in df.columns:
            df['descricao'] = df[desc_col].astype(str).fillna('')
        else:
            # Se não encontrou coluna de descrição, usa o valor como descrição
            df['descricao'] = df[valor_col].astype(str).fillna('')
    
    # Se a descrição for vazia ou apenas numérica, tenta usar outras colunas
    for idx, row in df.iterrows():
        if not df.loc[idx, 'descricao'] or df.loc[idx, 'descricao'] == 'nan':
            # Tenta outras colunas disponíveis
            for col in df.columns:
                if col not in ['data', 'valor', valor_col] and not pd.isna(row[col]):
                    df.loc[idx, 'descricao'] = str(row[col]).strip()
                    break
            # Se ainda está vazio, usa o valor como identificador
            if not df.loc[idx, 'descricao'] or df.loc[idx, 'descricao'] == 'nan':
                df.loc[idx, 'descricao'] = f"Custo {row[valor_col]}"

    df['entrada'] = 0.0
    
    # Debug: mostrar estatísticas do arquivo processado
    print(f"[DEBUG] Arquivo de saída processado - Linhas: {len(df)}, Total saídas: {df['saida'].sum():.2f}")
    
    return df