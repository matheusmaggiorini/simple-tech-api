from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import pandas as pd
import os
import sys
import numpy as np
from typing import Optional, Dict, Any

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from api.endpoints import state
from core.data_processing import processar_dados

# Criar diretório para uploads se não existir
if not os.path.exists(state.UPLOAD_DIR):
    os.makedirs(state.UPLOAD_DIR)

router = APIRouter()

class FileUploadResponse(BaseModel):
    message: str
    error: Optional[str] = None

def calcular_estatisticas_historicas(df: pd.DataFrame) -> Dict[str, Any]:
    if df.empty: return {}
    if "fluxo_diario" not in df.columns: df["fluxo_diario"] = df["entrada"] - df["saida"]
    stats = {
        "total_entradas": df["entrada"].sum(),
        "total_saidas": df["saida"].sum(),
        "media_entrada": df["entrada"].mean(),
        "media_saida": df["saida"].mean(),
        "desvio_padrao_entrada": df["entrada"].std(),
        "desvio_padrao_saida": df["saida"].std(),
        "media_fluxo": df["fluxo_diario"].mean(),
        "desvio_padrao_fluxo": df["fluxo_diario"].std(),
        "ultimo_saldo": df["saldo"].iloc[-1] if "saldo" in df.columns and not df.empty else 0.0,
        "data_atualizacao": pd.Timestamp.utcnow().isoformat(),
    }
    return {key: (float(value) if isinstance(value, (np.number, np.float64)) else value) for key, value in stats.items()}

def _read_multiple_sheets_outflow(upload: UploadFile) -> pd.DataFrame:
    """
    Lê arquivos de saída com múltiplas abas (cada aba = um dia do mês).
    Cada aba deve ter colunas: SAIDA, VALOR, Data
    Retorna DataFrame consolidado com todos os dados das abas.
    """
    filename = upload.filename or "arquivo_sem_nome"
    
    try:
        upload.file.seek(0)
        xls = pd.ExcelFile(upload.file)
        
        if not xls.sheet_names:
            raise ValueError(f"Arquivo {filename} não contém abas válidas")
        
        print(f"[DEBUG] Arquivo {filename} possui {len(xls.sheet_names)} abas: {xls.sheet_names}")
        
        all_dataframes = []
        
        for sheet_name in xls.sheet_names:
            try:
                upload.file.seek(0)
                df_sheet = pd.read_excel(upload.file, sheet_name=sheet_name)
                
                # Verifica se a aba tem dados
                if df_sheet.empty:
                    print(f"[DEBUG] Aba '{sheet_name}' está vazia - pulando")
                    continue
                
                # Normaliza nomes das colunas
                df_sheet.columns = [str(c).strip().lower() for c in df_sheet.columns]
                
                # Verifica se tem as colunas necessárias
                has_saida = 'saida' in df_sheet.columns
                has_valor = 'valor' in df_sheet.columns
                has_data = 'data' in df_sheet.columns
                
                if not (has_saida and has_valor and has_data):
                    print(f"[DEBUG] Aba '{sheet_name}' não tem colunas SAIDA, VALOR e Data - pulando")
                    continue
                
                # Processa os dados da aba
                df_processed = df_sheet.copy()
                
                # Processa valores monetários - usa coluna 'valor' para o valor monetário
                df_processed['saida'] = _normalizar_valores_monetarios_series(df_processed['valor'])
                # Usa coluna 'saida' original para descrição
                df_processed['descricao'] = df_processed['saida'].astype(str).fillna('')
                df_processed['entrada'] = 0.0
                
                # Processa data
                df_processed['data'] = _converter_coluna_data_excel(df_processed['data'])
                
                # Remove linhas inválidas
                df_processed = df_processed[pd.to_numeric(df_processed['saida'], errors='coerce').fillna(0) > 0].copy()
                df_processed = df_processed.dropna(how='all').copy()
                df_processed = df_processed.dropna(subset=['data']).copy()
                
                if not df_processed.empty:
                    # Adiciona informação da aba para debug
                    df_processed['aba_origem'] = sheet_name
                    all_dataframes.append(df_processed)
                    print(f"[DEBUG] Aba '{sheet_name}' processada - {len(df_processed)} linhas válidas")
                
            except Exception as e:
                print(f"[WARNING] Erro ao processar aba '{sheet_name}': {e}")
                continue
        
        if not all_dataframes:
            print(f"[WARNING] Nenhuma aba válida encontrada em {filename}")
            return pd.DataFrame(columns=['data', 'saida', 'descricao', 'entrada'])
        
        # Concatena todos os DataFrames das abas
        df_consolidado = pd.concat(all_dataframes, ignore_index=True)
        print(f"[DEBUG] Arquivo {filename} consolidado - {len(df_consolidado)} linhas de {len(all_dataframes)} abas")
        
        return df_consolidado
        
    except Exception as e:
        print(f"[ERROR] Erro ao ler arquivo {filename} com múltiplas abas: {e}")
        raise ValueError(f"Erro ao ler arquivo {filename}: {str(e)}")

def _normalizar_valores_monetarios_series(serie: pd.Series) -> pd.Series:
    """Normaliza valores monetários brasileiros"""
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
        
        try:
            return float(str_val)
        except:
            return 0.0
    
    return serie.apply(normalize_single_value)

def _converter_coluna_data_excel(col: pd.Series) -> pd.Series:
    """Converte coluna de data do Excel para datetime"""
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

def _read_any_cashflow_table(upload: UploadFile, treat_outflow_layout: bool = False) -> pd.DataFrame:
    """Lê uma planilha enviada (xlsx/xls/csv) e retorna um DataFrame com
    as colunas referentes a fluxo de caixa. Tenta ser tolerante a variações:
    - .xlsx/.xls: tenta a aba 'FluxoDeCaixa'; se não existir, usa a primeira aba
    - .csv: detecta separador automaticamente
    - corrige coluna 'Unnamed: 0' -> 'data'
    - quando treat_outflow_layout=True, tenta mapear CSVs do card de saída (último VALOR como saida e coluna 'SAIDA' como descrição)
    """
    filename = upload.filename or "arquivo_sem nome"
    lower = filename.lower()

    try:
        if lower.endswith('.csv'):
            # Tenta separadores comuns; usa o primeiro que gerar colunas > 1
            upload.file.seek(0)
            df = None
            for sep in [';', ',', '\t', '|']:
                upload.file.seek(0)
                try:
                    df_csv = pd.read_csv(upload.file, sep=sep, encoding='utf-8')
                    if df_csv.shape[1] > 1:
                        df = df_csv
                        break
                except UnicodeDecodeError:
                    # Tenta com encoding latin-1 se utf-8 falhar
                    upload.file.seek(0)
                    try:
                        df_csv = pd.read_csv(upload.file, sep=sep, encoding='latin-1')
                        if df_csv.shape[1] > 1:
                            df = df_csv
                            break
                    except Exception:
                        continue
                except Exception:
                    continue
            
            if df is None:
                # Último recurso sem separador
                upload.file.seek(0)
                try:
                    df = pd.read_csv(upload.file, encoding='utf-8')
                except UnicodeDecodeError:
                    upload.file.seek(0)
                    df = pd.read_csv(upload.file, encoding='latin-1')
        else:
            # Excel: tenta aba específica e depois a primeira
            upload.file.seek(0)
            try:
                df = pd.read_excel(upload.file, sheet_name='FluxoDeCaixa')
            except Exception:
                upload.file.seek(0)
                # Lê a primeira aba disponível
                xls = pd.ExcelFile(upload.file)
                if not xls.sheet_names:
                    raise ValueError(f"Arquivo {filename} não contém abas válidas")
                first_sheet = xls.sheet_names[0]
                upload.file.seek(0)
                df = pd.read_excel(upload.file, sheet_name=first_sheet)
                
        # Verifica se o DataFrame está vazio
        if df.empty:
            raise ValueError(f"Arquivo {filename} está vazio ou não contém dados válidos")
            
    except Exception as e:
        print(f"[ERROR] Erro ao ler arquivo {filename}: {str(e)}")
        raise ValueError(f"Erro ao ler arquivo {filename}: {str(e)}")

    # Normalizações de colunas
    if 'Unnamed: 0' in df.columns:
        df.rename(columns={'Unnamed: 0': 'data'}, inplace=True)
    # Tenta padronizar nomes comuns
    df.columns = [str(c).strip() for c in df.columns]
    # Índice auxiliar para buscas case-insensitive
    lower_to_original = {str(c).strip().lower(): c for c in df.columns}
    possible_data = [c for c in df.columns if c.lower() in ['data', 'date']]
    if 'data' not in df.columns and possible_data:
        df.rename(columns={possible_data[0]: 'data'}, inplace=True)
    
    # Normaliza colunas para minúsculo para processamento consistente
    df.columns = [str(c).strip().lower() for c in df.columns]

    possible_desc = [c for c in df.columns if c.lower() in ['descricao', 'descrição', 'description', 'historico', 'histórico']]
    if 'descricao' not in df.columns and possible_desc:
        df.rename(columns={possible_desc[0]: 'descricao'}, inplace=True)

    # Tenta localizar colunas de entrada/saída por nomes comuns
    def _rename_first(candidates, target):
        for c in df.columns:
            if str(c).lower() in candidates:
                if target not in df.columns:
                    df.rename(columns={c: target}, inplace=True)
                break

    _rename_first({'entrada', 'entradas', 'receita', 'receitas', 'recebimento', 'recebimentos', 'inflow', 'creditos', 'créditos', 'credito', 'crédito'}, 'entrada')
    _rename_first({'saida', 'saída', 'saidas', 'saídas', 'despesa', 'despesas', 'pagamento', 'pagamentos', 'outflow', 'debito', 'débitos', 'débito', 'debitos'}, 'saida')

    # Tratamento especial para layout de SAÍDA (card 2)
    if treat_outflow_layout:
        headers_lower = [str(h).lower().strip() for h in df.columns]
        if ('data' in lower_to_original or 'data' in df.columns) and headers_lower.count('valor') >= 1:
            valor_cols = [c for c in df.columns if str(c).strip().lower() == 'valor']
            valor_col = valor_cols[-1]
            
            # Processa valores monetários brasileiros (R$ X.XXX,XX)
            serie = df[valor_col].astype(str)
            # Remove R$ e espaços, mantém apenas números, pontos, vírgulas e hífens
            serie = serie.str.replace(r'[^0-9,.-]', '', regex=True)
            # Remove pontos (milhares) e substitui vírgula por ponto (decimal)
            serie = serie.str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
            df['saida'] = pd.to_numeric(serie, errors='coerce').fillna(0)
            
            # descrição: procura por colunas de descrição (SAIDA, FORMA, etc.)
            saida_desc_col = None
            # Tenta encontrar coluna de descrição por nomes comuns
            for desc_name in ['saida', 'forma', 'descricao', 'descrição', 'fornecedor', 'cliente']:
                if desc_name in lower_to_original:
                    saida_desc_col = lower_to_original[desc_name]
                    break
            
            # Se não encontrou, tenta a coluna anterior ao VALOR
            if saida_desc_col is None:
                try:
                    idx = list(df.columns).index(valor_col)
                    saida_desc_col = list(df.columns)[idx - 1] if idx - 1 >= 0 else None
                except Exception:
                    saida_desc_col = None
            
            # Verifica se a coluna existe antes de usar
            if saida_desc_col and saida_desc_col in df.columns:
                df['descricao'] = df[saida_desc_col].astype(str)
            else:
                df['descricao'] = ''
            
            # normaliza data - formato DD/M (sem ano)
            if 'data' in df.columns:
                # Converte para string primeiro para processar formato DD/M
                df['data'] = df['data'].astype(str)
                # Adiciona ano atual se não estiver presente
                current_year = pd.Timestamp.now().year
                df['data'] = df['data'].apply(lambda x: f"{x}/{current_year}" if '/' in x and len(x.split('/')) == 2 else x)
                df['data'] = pd.to_datetime(df['data'], errors='coerce', dayfirst=True)
            
            # manter apenas linhas com saida > 0 e que não sejam completamente vazias
            df = df[pd.to_numeric(df['saida'], errors='coerce').fillna(0) > 0].copy()
            # Remover linhas completamente vazias (todas as colunas são NaN ou vazias)
            df = df.dropna(how='all').copy()
            
            # Verificar se ainda há dados válidos após a limpeza
            if df.empty:
                print(f"[WARNING] Arquivo {filename} está vazio após processamento - retornando DataFrame vazio")
                # Retorna DataFrame vazio com estrutura correta em vez de erro
                empty_df = pd.DataFrame(columns=['data', 'saida', 'descricao', 'entrada'])
                return empty_df
            
            df['entrada'] = 0.0
            try:
                print('[OUTFLOW DETECT]', filename, 'linhas:', len(df), 'saida_sum:', float(df['saida'].sum()))
            except Exception:
                pass
            return df
    
    # Detecção automática de arquivos de saída por nome
    is_outflow_by_name = filename and any(keyword in filename.lower() for keyword in [
        'saida', 'saída', 'fevereiro', 'janeiro', 'março', 'abril', 'maio', 'junho', 
        'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro', 'cópia', 'copy'
    ])
    
    # Detecção automática por estrutura (DATA + VALOR sem ENTRADA)
    has_data_and_valor = ('data' in df.columns) and any('valor' == c for c in df.columns)
    has_entrada_col = 'entrada' in df.columns
    has_saida_col = 'saida' in df.columns
    
    if (is_outflow_by_name or (has_data_and_valor and not has_entrada_col and not has_saida_col)) and not treat_outflow_layout:
        print(f"[DEBUG] Detectado arquivo de saída por nome/estrutura: {filename}")
        # Aplica o mesmo tratamento de saída
        headers_lower = [str(h).lower().strip() for h in df.columns]
        if ('data' in lower_to_original or 'data' in df.columns) and headers_lower.count('valor') >= 1:
            valor_cols = [c for c in df.columns if str(c).strip().lower() == 'valor']
            valor_col = valor_cols[-1]
            
            # Processa valores monetários brasileiros (R$ X.XXX,XX)
            serie = df[valor_col].astype(str)
            # Remove R$ e espaços, mantém apenas números, pontos, vírgulas e hífens
            serie = serie.str.replace(r'[^0-9,.-]', '', regex=True)
            # Remove pontos (milhares) e substitui vírgula por ponto (decimal)
            serie = serie.str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
            df['saida'] = pd.to_numeric(serie, errors='coerce').fillna(0)
            
            # descrição: procura por colunas de descrição (SAIDA, FORMA, etc.)
            saida_desc_col = None
            # Tenta encontrar coluna de descrição por nomes comuns
            for desc_name in ['saida', 'forma', 'descricao', 'descrição', 'fornecedor', 'cliente']:
                if desc_name in lower_to_original:
                    saida_desc_col = lower_to_original[desc_name]
                    break
            
            # Se não encontrou, tenta a coluna anterior ao VALOR
            if saida_desc_col is None:
                try:
                    idx = list(df.columns).index(valor_col)
                    saida_desc_col = list(df.columns)[idx - 1] if idx - 1 >= 0 else None
                except Exception:
                    saida_desc_col = None
            
            # Verifica se a coluna existe antes de usar
            if saida_desc_col and saida_desc_col in df.columns:
                df['descricao'] = df[saida_desc_col].astype(str)
            else:
                df['descricao'] = ''
            
            # normaliza data - formato DD/M (sem ano)
            if 'data' in df.columns:
                # Converte para string primeiro para processar formato DD/M
                df['data'] = df['data'].astype(str)
                # Adiciona ano atual se não estiver presente
                current_year = pd.Timestamp.now().year
                df['data'] = df['data'].apply(lambda x: f"{x}/{current_year}" if '/' in x and len(x.split('/')) == 2 else x)
                df['data'] = pd.to_datetime(df['data'], errors='coerce', dayfirst=True)
            
            # manter apenas linhas com saida > 0
            df = df[pd.to_numeric(df['saida'], errors='coerce').fillna(0) > 0].copy()
            df = df.dropna(how='all').copy()
            
            if df.empty:
                print(f"[WARNING] Arquivo {filename} está vazio após processamento - retornando DataFrame vazio")
                # Retorna DataFrame vazio com estrutura correta em vez de erro
                empty_df = pd.DataFrame(columns=['data', 'saida', 'descricao', 'entrada'])
                return empty_df
            
            df['entrada'] = 0.0
            print(f'[AUTO-OUTFLOW DETECT] {filename} - linhas: {len(df)}, saida_sum: {float(df["saida"].sum()):.2f}')
            return df

    # Heurística específica: planilhas de ENTRADA onde o valor está em uma coluna de total pago/recebido
    if 'entrada' not in df.columns:
        entrada_candidates = [
            'valor pago', 'valor_pago', 'valor 0pago',  # inclui possível espaço inquebrável
            'total final', 'total_final',
            'valor recebido', 'valor_recebido',
            'valor total', 'valor_total', 'vl total', 'vl_total',
            'valor pago (r$)', 'valor pago r$', 'r$ valor pago'
        ]
        for candidate in entrada_candidates:
            if candidate in lower_to_original:
                df.rename(columns={lower_to_original[candidate]: 'entrada'}, inplace=True)
                break

    # Normaliza a coluna 'entrada' textual em moeda brasileira para número
    if 'entrada' in df.columns:
        serie = df['entrada'].astype(str)
        # Remove qualquer caractere não numérico relevante
        serie = serie.str.replace(r'[^0-9,.-]', '', regex=True)
        # Se houver ponto e vírgula, trata ponto como milhar e vírgula como decimal
        tem_ponto = serie.str.contains(r'\.', regex=False)
        tem_virgula = serie.str.contains(',', regex=False)
        ambos = tem_ponto & tem_virgula
        serie = serie.where(~ambos, serie.str.replace('.', '', regex=False))
        serie = serie.where(~ambos, serie.str.replace(',', '.', regex=False))
        somente_virgula = ~tem_ponto & tem_virgula
        serie = serie.where(~somente_virgula, serie.str.replace(',', '.', regex=False))
        df['entrada'] = pd.to_numeric(serie, errors='coerce').fillna(0)

    # NÃO filtra por cancelamento: manter todas as linhas para evitar perdas de meses

    return df


# --- ENDPOINT TOLERANTE PARA UPLOAD DE ARQUIVOS ---
@router.post("/upload_excel_bundle", response_model=FileUploadResponse)
async def upload_excel_bundle(file: UploadFile | None = File(None), files: list[UploadFile] | None = File(None), has_outflow: bool = Form(False)):
    """
    Aceita:
    - Um único arquivo (campo 'file') OU múltiplos (campo 'files').
    - Excel (.xlsx/.xls) com ou sem a aba 'FluxoDeCaixa'. Se não existir, usa a primeira aba.
    - CSV com diferentes separadores. Se houver apenas uma planilha, assume que entradas e saídas estão nela.
    Consolida tudo e processa.
    """
    uploads: list[UploadFile] = []
    if files and len(files) > 0:
        uploads = files
    elif file is not None:
        uploads = [file]
    else:
        raise HTTPException(status_code=400, detail="Nenhum arquivo enviado.")

    try:
        dataframes: list[pd.DataFrame] = []
        filenames: list[str] = []
        
        for up in uploads:
            print(f"Processando arquivo recebido: {up.filename}")
            try:
                # Verifica se o arquivo não está vazio
                if up.size == 0:
                    print(f"[WARNING] Arquivo {up.filename} está vazio - pulando")
                    continue
                
                # Detecta automaticamente se é arquivo de saída baseado no nome
                filename_lower = (up.filename or "").lower()
                is_outflow_file = any(keyword in filename_lower for keyword in [
                    'saida', 'saída', 'fevereiro', 'janeiro', 'março', 'abril', 'maio', 'junho', 
                    'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro', 'cópia'
                ])
                
                # Usa detecção automática ou o parâmetro has_outflow
                treat_as_outflow = is_outflow_file or bool(has_outflow)
                print(f"[DEBUG] Arquivo {up.filename} - tratado como saída: {treat_as_outflow}")
                
                # Verifica se é um arquivo Excel com múltiplas abas (arquivo de saída mensal)
                is_excel_file = filename_lower.endswith(('.xlsx', '.xls'))
                has_multiple_sheets = False
                
                if is_excel_file and treat_as_outflow:
                    try:
                        # Verifica se tem múltiplas abas
                        up.file.seek(0)
                        xls = pd.ExcelFile(up.file)
                        has_multiple_sheets = len(xls.sheet_names) > 1
                        print(f"[DEBUG] Arquivo {up.filename} - múltiplas abas: {has_multiple_sheets} ({len(xls.sheet_names)} abas)")
                    except Exception as e:
                        print(f"[DEBUG] Erro ao verificar abas do arquivo {up.filename}: {e}")
                        has_multiple_sheets = False
                
                # Escolhe a função de leitura apropriada
                if has_multiple_sheets and treat_as_outflow:
                    print(f"[DEBUG] Usando leitura de múltiplas abas para {up.filename}")
                    df_single = _read_multiple_sheets_outflow(up)
                else:
                    df_single = _read_any_cashflow_table(up, treat_outflow_layout=treat_as_outflow)
                print("Colunas lidas:", df_single.columns.tolist())
                
                # Verifica se o DataFrame não está vazio
                if df_single.empty:
                    print(f"[WARNING] Arquivo {up.filename} resultou em DataFrame vazio - pulando")
                    continue
                    
                dataframes.append(df_single)
                filenames.append(up.filename or "arquivo_sem_nome")
                
            except Exception as e:
                print(f"[ERROR] Erro ao ler arquivo {up.filename}: {str(e)}")
                # Continua processando outros arquivos mesmo se um falhar
                continue

        if not dataframes:
            raise HTTPException(status_code=400, detail="Nenhuma tabela de dados foi extraída dos arquivos enviados.")

        # Processa cada arquivo individualmente para detectar corretamente entrada/saída
        processed_dataframes: list[pd.DataFrame] = []
        for i, (df, filename) in enumerate(zip(dataframes, filenames)):
            print(f"[DEBUG] Processando arquivo {i+1}/{len(dataframes)}: {filename}")
            print(f"[DEBUG] Colunas antes do processamento: {list(df.columns)}")
            try:
                df_processed = processar_dados(df, filename)
                # Só adiciona se o DataFrame não estiver vazio
                if not df_processed.empty:
                    processed_dataframes.append(df_processed)
                    entradas = df_processed.get('entrada', pd.Series([0])).sum()
                    saidas = df_processed.get('saida', pd.Series([0])).sum()
                    print(f"[DEBUG] Arquivo {filename} - Entradas: {entradas:.2f}, Saídas: {saidas:.2f}")
                    print(f"[DEBUG] Colunas após processamento: {list(df_processed.columns)}")
                else:
                    print(f"[DEBUG] Arquivo {filename} está vazio - pulando")
            except Exception as e:
                print(f"[DEBUG] Erro ao processar {filename}: {e}")
                # Se é um arquivo vazio, continua sem erro
                if "não contém dados válidos" in str(e).lower() or "vazio" in str(e).lower():
                    print(f"[DEBUG] Arquivo {filename} vazio - continuando")
                    continue
                else:
                    # Para outros erros, também continua processando outros arquivos
                    print(f"[WARNING] Erro no arquivo {filename}, continuando com outros arquivos")
                    continue

        if not processed_dataframes:
            raise HTTPException(status_code=400, detail="Nenhum arquivo contém dados válidos para processamento.")
        
        try:
            print(f"[DEBUG] Concatenando {len(processed_dataframes)} DataFrames processados")
            df_concat = pd.concat(processed_dataframes, ignore_index=True)
            print(f"[DEBUG] DataFrame concatenado - Linhas: {len(df_concat)}, Colunas: {list(df_concat.columns)}")
            
            if df_concat.empty:
                raise HTTPException(status_code=400, detail="Os arquivos enviados não contêm dados.")

            # Aplica processamento final para consolidar dados
            print("[DEBUG] Aplicando processamento final de consolidação...")
            # NÃO chama processar_dados novamente, pois os dados já foram processados individualmente
            # Apenas garante que as colunas essenciais existam
            df_processed = df_concat.copy()
            
            # Garante que as colunas essenciais existam
            if 'entrada' not in df_processed.columns:
                df_processed['entrada'] = 0.0
            if 'saida' not in df_processed.columns:
                df_processed['saida'] = 0.0
            if 'fluxo_diario' not in df_processed.columns:
                df_processed['fluxo_diario'] = df_processed['entrada'] - df_processed['saida']
            if 'saldo' not in df_processed.columns:
                df_processed['saldo'] = df_processed['fluxo_diario'].cumsum()
            
            print(f"[DEBUG] Após consolidação final - Linhas: {len(df_processed)}, Colunas: {list(df_processed.columns)}")
            
            # DEBUG: sumarização rápida para diagnosticar zeros
            try:
                total_e = float(pd.to_numeric(df_processed.get('entrada', 0), errors='coerce').fillna(0).sum())
                total_s = float(pd.to_numeric(df_processed.get('saida', 0), errors='coerce').fillna(0).sum())
                qtd_e_pos = int((pd.to_numeric(df_processed.get('entrada', 0), errors='coerce') > 0).sum())
                qtd_s_pos = int((pd.to_numeric(df_processed.get('saida', 0), errors='coerce') > 0).sum())
                print("[DEBUG] RESUMO FINAL:")
                print(f"[DEBUG] Total entrada: {total_e:.2f}")
                print(f"[DEBUG] Total saída: {total_s:.2f}")
                print(f"[DEBUG] Qtd entradas > 0: {qtd_e_pos}")
                print(f"[DEBUG] Qtd saídas > 0: {qtd_s_pos}")
                
                if 'data' in df_processed.columns:
                    tmp = df_processed.copy()
                    tmp['ano_mes'] = tmp['data'].dt.to_period('M')
                    resumo = tmp.groupby('ano_mes').agg(entrada=('entrada', 'sum'), saida=('saida', 'sum')).head(12)
                    print("[DEBUG] Entradas/Saídas por mês (primeiros 12):\n", resumo)
            except Exception as _:
                pass
                
            state.global_processed_df = df_processed
            state.global_historical_stats = calcular_estatisticas_historicas(df_processed)
            state.global_prediction_model = None
            state.global_feature_importance = None
            print("Dados de fluxo de caixa processados e salvos no estado.")
            return FileUploadResponse(message="Arquivo(s) processado(s) com sucesso!")
            
        except Exception as concat_error:
            print(f"[ERROR] Erro ao concatenar DataFrames: {str(concat_error)}")
            raise HTTPException(status_code=500, detail=f"Erro ao processar dados: {str(concat_error)}")

    except ValueError as ve:
        print(f"[ERROR] ValueError: {str(ve)}")
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        # Re-raise HTTPException para manter o status code correto
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[ERROR] Erro interno: {str(e)}")
        print(f"[ERROR] Traceback: {error_trace}")
        return JSONResponse(status_code=500, content={"message": "Erro interno do servidor", "error": str(e)})


@router.get("/view_processed")
async def view_processed_data(limit: int = 50):
    """Retorna uma prévia dos dados de fluxo de caixa carregados."""
    if state.global_processed_df is None or state.global_processed_df.empty:
        raise HTTPException(status_code=404, detail="Nenhum dado de fluxo de caixa processado.")

    df_src = state.global_processed_df
    if limit is None or limit <= 0 or limit >= len(df_src):
        df_copy = df_src.copy()
    else:
        df_copy = df_src.head(limit).copy()
    for col in df_copy.select_dtypes(include=['datetime64[ns]']).columns:
        df_copy[col] = df_copy[col].dt.strftime('%Y-%m-%d')
    df_copy = df_copy.replace({np.nan: None})
    return JSONResponse(content=df_copy.to_dict(orient="records"))


@router.get("/statistics")
async def get_statistics():
    """Retorna as estatísticas históricas calculadas."""
    if state.global_historical_stats is None:
        raise HTTPException(
            status_code=404, 
            detail="Nenhuma estatística calculada. Faça o upload dos dados primeiro."
        )
    
    return JSONResponse(content=state.global_historical_stats)


@router.get("/monthly_summary")
async def get_monthly_summary(limit: int | None = None):
    """Resumo mensal de entradas e saídas direto do backend.
    Retorna [{ano_mes: 'YYYY-MM', entrada: float, saida: float, qtd_entradas_pos: int, qtd_saidas_pos: int}]."""
    if state.global_processed_df is None or state.global_processed_df.empty:
        raise HTTPException(status_code=404, detail="Nenhum dado processado.")

    df = state.global_processed_df
    tmp = df.copy()
    if 'data' not in tmp.columns:
        raise HTTPException(status_code=400, detail="Coluna 'data' ausente após processamento.")
    tmp['ano_mes'] = tmp['data'].dt.to_period('M')
    tmp['entrada_num'] = pd.to_numeric(tmp.get('entrada', 0), errors='coerce').fillna(0)
    tmp['saida_num'] = pd.to_numeric(tmp.get('saida', 0), errors='coerce').fillna(0)
    grouped = tmp.groupby('ano_mes').agg(
        entrada=('entrada_num', 'sum'),
        saida=('saida_num', 'sum'),
        qtd_entradas_pos=('entrada_num', lambda s: int((s > 0).sum())),
        qtd_saidas_pos=('saida_num', lambda s: int((s > 0).sum())),
    ).reset_index()
    grouped['ano_mes'] = grouped['ano_mes'].astype(str)
    if limit and limit > 0:
        grouped = grouped.head(limit)
    return JSONResponse(content=grouped.to_dict(orient='records'))