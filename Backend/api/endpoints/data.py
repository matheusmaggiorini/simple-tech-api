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

    if lower.endswith('.csv'):
        # Tenta separadores comuns; usa o primeiro que gerar colunas > 1
        upload.file.seek(0)
        for sep in [';', ',', '\t', '|']:
            upload.file.seek(0)
            try:
                df_csv = pd.read_csv(upload.file, sep=sep)
                if df_csv.shape[1] > 1:
                    break
            except Exception:
                continue
        else:
            # Último recurso sem separador
            upload.file.seek(0)
            df_csv = pd.read_csv(upload.file)
        df = df_csv
    else:
        # Excel: tenta aba específica e depois a primeira
        upload.file.seek(0)
        try:
            df = pd.read_excel(upload.file, sheet_name='FluxoDeCaixa')
        except Exception:
            upload.file.seek(0)
            # Lê a primeira aba disponível
            xls = pd.ExcelFile(upload.file)
            first_sheet = xls.sheet_names[0]
            upload.file.seek(0)
            df = pd.read_excel(upload.file, sheet_name=first_sheet)

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
            serie = df[valor_col].astype(str)
            serie = serie.str.replace(r'[^0-9,.-]', '', regex=True)
            serie = serie.str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
            df['saida'] = pd.to_numeric(serie, errors='coerce').fillna(0)
            # descrição: coluna 'SAIDA' (quando presente no card 2)
            saida_desc_col = lower_to_original.get('saida')
            if saida_desc_col is None:
                try:
                    idx = list(df.columns).index(valor_col)
                    saida_desc_col = list(df.columns)[idx - 1] if idx - 1 >= 0 else None
                except Exception:
                    saida_desc_col = None
            df['descricao'] = df[saida_desc_col].astype(str) if saida_desc_col else ''
            # normaliza data
            data_col = lower_to_original.get('data', 'data')
            if pd.api.types.is_integer_dtype(df[data_col]) or pd.api.types.is_float_dtype(df[data_col]):
                df['data'] = pd.to_datetime(df[data_col], origin='1899-12-30', unit='D', errors='coerce')
            else:
                df['data'] = pd.to_datetime(df[data_col], errors='coerce', dayfirst=True)
            # manter apenas linhas com saida > 0 e que não sejam completamente vazias
            df = df[pd.to_numeric(df['saida'], errors='coerce').fillna(0) > 0].copy()
            # Remover linhas completamente vazias (todas as colunas são NaN ou vazias)
            df = df.dropna(how='all').copy()
            
            # Verificar se ainda há dados válidos após a limpeza
            if df.empty:
                raise ValueError(f"Arquivo {filename} não contém dados válidos após processamento.")
            
            df['entrada'] = 0.0
            try:
                print('[OUTFLOW DETECT]', filename, 'linhas:', len(df), 'saida_sum:', float(df['saida'].sum()))
            except Exception:
                pass
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
        tem_ponto = serie.str.contains('\.', regex=False)
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
        for up in uploads:
            print(f"Processando arquivo recebido: {up.filename}")
            df_single = _read_any_cashflow_table(up, treat_outflow_layout=bool(has_outflow))
            print("Colunas lidas:", df_single.columns.tolist())
            dataframes.append(df_single)

        if not dataframes:
            raise HTTPException(status_code=400, detail="Nenhuma tabela de dados foi extraída dos arquivos enviados.")

        df_concat = pd.concat(dataframes, ignore_index=True)
        if df_concat.empty:
            raise HTTPException(status_code=400, detail="Os arquivos enviados não contêm dados.")

        df_processed = processar_dados(df_concat)
        # DEBUG: sumarização rápida para diagnosticar zeros
        try:
            total_e = float(pd.to_numeric(df_processed.get('entrada', 0), errors='coerce').fillna(0).sum())
            total_s = float(pd.to_numeric(df_processed.get('saida', 0), errors='coerce').fillna(0).sum())
            qtd_e_pos = int((pd.to_numeric(df_processed.get('entrada', 0), errors='coerce') > 0).sum())
            print("[DEBUG] Total entrada:", total_e, "Total saída:", total_s, "Qtd entradas > 0:", qtd_e_pos)
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

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        import traceback
        print(traceback.format_exc())
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