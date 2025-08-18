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
from core.supabase_client import supabase
from core.data_processing import processar_dados

# Criar diretório para uploads se não existir
if not os.path.exists(state.UPLOAD_DIR):
    os.makedirs(state.UPLOAD_DIR)

router = APIRouter()

class FileUploadResponse(BaseModel):
    filename: str
    message: str
    error: Optional[str] = None

def calcular_estatisticas_historicas(df: pd.DataFrame) -> Dict[str, Any]:
    """Calcula estatísticas básicas do DataFrame para uso nas simulações."""
    if df.empty:
        return {}
    
    if "fluxo_diario" not in df.columns:
        df["fluxo_diario"] = df["entrada"] - df["saida"]

    stats = {
        "media_entrada": df["entrada"].mean(),
        "media_saida": df["saida"].mean(),
        "desvio_padrao_entrada": df["entrada"].std(),
        "desvio_padrao_saida": df["saida"].std(),
        "media_fluxo": df["fluxo_diario"].mean(),
        "desvio_padrao_fluxo": df["fluxo_diario"].std(),
        "ultimo_saldo": df["saldo_acumulado"].iloc[-1] if "saldo_acumulado" in df.columns and not df.empty else 0.0,
        "ultima_data": df["data"].max()
    }
    # --- A CORREÇÃO ESTÁ AQUI ---
    # Trocamos o np.float_ (antigo) por np.float64 (novo)
    return {key: (float(value) if isinstance(value, (np.number, np.float64)) else value) for key, value in stats.items()}

@router.post("/upload_csv", response_model=FileUploadResponse)
async def upload_csv_file(file: UploadFile = File(...)):
    """Recebe, processa e armazena os dados do arquivo CSV."""
    try:
        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="Arquivo deve ser do tipo CSV")
        
        file_path = os.path.join(state.UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        df_raw = pd.read_csv(file_path, sep=None, engine='python')
        
        if df_raw.empty:
            raise HTTPException(status_code=400, detail="O arquivo CSV está vazio.")
            
        df_processed = processar_dados(df_raw)

        if df_processed is None or df_processed.empty:
            raise HTTPException(status_code=400, detail="Erro ao processar o arquivo. Verifique o formato e as colunas.")

        print("Salvando DataFrame processado no estado global.")
        state.global_processed_df = df_processed
        
        state.global_historical_stats = calcular_estatisticas_historicas(df_processed)
        print("Estatísticas históricas calculadas e salvas.")
        
        state.global_prediction_model = None

        try:
            if supabase:
                print("Tentando salvar dados no Supabase...")
                df_to_send = df_processed.copy()
                for col in df_to_send.select_dtypes(include=['datetime64[ns]']).columns:
                    df_to_send[col] = df_to_send[col].dt.isoformat()
                df_dict = df_to_send.replace({np.nan: None}).to_dict(orient='records')

                supabase.table('transacoes').delete().neq('id', -1).execute()
                supabase.table('transacoes').insert(df_dict).execute()
                print("Dados salvos no Supabase com sucesso.")
        except Exception as e:
            print(f"AVISO: Falha ao salvar no Supabase. Erro: {e}")

        return FileUploadResponse(
            filename=file.filename,
            message="Arquivo processado e dados carregados com sucesso!"
        )

    except HTTPException as http_exc:
        return JSONResponse(status_code=http_exc.status_code, content={"filename": file.filename, "message": "Erro de validação", "error": http_exc.detail})
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JSONResponse(status_code=500, content={"filename": file.filename, "message": "Erro interno do servidor", "error": str(e)})


@router.get("/view_processed")
async def view_processed_data(limit: int = 10):
    """Retorna uma prévia dos dados que estão atualmente carregados no estado global."""
    if state.global_processed_df is None or state.global_processed_df.empty:
        raise HTTPException(
            status_code=404,
            detail="Nenhum dado processado disponível. Faça o upload de um arquivo primeiro."
        )

    df_copy = state.global_processed_df.head(limit).copy()
    
    for col in df_copy.select_dtypes(include=['datetime64[ns]']).columns:
        df_copy[col] = df_copy[col].dt.strftime('%Y-%m-%d')
    
    df_copy = df_copy.replace({np.nan: None})
    
    return JSONResponse(content=df_copy.to_dict(orient="records"))