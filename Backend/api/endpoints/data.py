from fastapi import APIRouter, UploadFile, File, HTTPException
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

def _read_any_cashflow_table(upload: UploadFile) -> pd.DataFrame:
    """Lê uma planilha enviada (xlsx/xls/csv) e retorna um DataFrame com
    as colunas referentes a fluxo de caixa. Tenta ser tolerante a variações:
    - .xlsx/.xls: tenta a aba 'FluxoDeCaixa'; se não existir, usa a primeira aba
    - .csv: detecta separador automaticamente
    - corrige coluna 'Unnamed: 0' -> 'data'
    """
    filename = upload.filename or "arquivo_sem_nome"
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

    return df


# --- ENDPOINT TOLERANTE PARA UPLOAD DE ARQUIVOS ---
@router.post("/upload_excel_bundle", response_model=FileUploadResponse)
async def upload_excel_bundle(file: UploadFile | None = File(None), files: list[UploadFile] | None = File(None)):
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
            df_single = _read_any_cashflow_table(up)
            print("Colunas lidas:", df_single.columns.tolist())
            dataframes.append(df_single)

        if not dataframes:
            raise HTTPException(status_code=400, detail="Nenhuma tabela de dados foi extraída dos arquivos enviados.")

        df_concat = pd.concat(dataframes, ignore_index=True)
        if df_concat.empty:
            raise HTTPException(status_code=400, detail="Os arquivos enviados não contêm dados.")

        df_processed = processar_dados(df_concat)
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

    df_copy = state.global_processed_df.head(limit).copy()
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