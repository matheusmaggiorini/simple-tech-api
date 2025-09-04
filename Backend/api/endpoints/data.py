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
from core.financial_metrics import calcular_prazos_medios

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
        "media_entrada": df["entrada"].mean(),
        "media_saida": df["saida"].mean(),
        "desvio_padrao_entrada": df["entrada"].std(),
        "desvio_padrao_saida": df["saida"].std(),
        "media_fluxo": df["fluxo_diario"].mean(),
        "desvio_padrao_fluxo": df["fluxo_diario"].std(),
        "ultimo_saldo": df["saldo"].iloc[-1] if "saldo" in df.columns and not df.empty else 0.0,
    }
    return {key: (float(value) if isinstance(value, (np.number, np.float64)) else value) for key, value in stats.items()}

# --- ENDPOINT INTELIGENTE PARA UPLOAD DE EXCEL ---
@router.post("/upload_excel_bundle", response_model=FileUploadResponse)
async def upload_excel_bundle(file: UploadFile = File(...)):
    """
    Recebe UM ÚNICO arquivo Excel (.xlsx) com duas abas: 'FluxoDeCaixa' e 'DadosContabeis'.
    Processa ambas as abas e armazena todos os resultados no estado global.
    """
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(status_code=400, detail="O arquivo deve ser do tipo Excel (.xlsx)")

    try:
        # --- Processamento da Aba de Fluxo de Caixa ---
        print("Lendo a aba 'FluxoDeCaixa' do arquivo Excel...")
        df_raw_cashflow = pd.read_excel(file.file, sheet_name='FluxoDeCaixa')
        
        # Diagnóstico e correção de colunas
        print("Colunas originais lidas do Excel:", df_raw_cashflow.columns.tolist())

        # Renomear a coluna problemática de 'Unnamed: 0' para 'data'
        if 'Unnamed: 0' in df_raw_cashflow.columns:
            df_raw_cashflow.rename(columns={'Unnamed: 0': 'data'}, inplace=True)
            print("Coluna 'Unnamed: 0' foi renomeada para 'data'.")
      
        print("Colunas Finais:", df_raw_cashflow.columns.tolist())
        if df_raw_cashflow.empty:
            raise HTTPException(status_code=400, detail="A aba 'FluxoDeCaixa' está vazia.")
        
        df_processed = processar_dados(df_raw_cashflow)
        state.global_processed_df = df_processed
        state.global_historical_stats = calcular_estatisticas_historicas(df_processed)
        state.global_prediction_model = None  # Reset do modelo quando novos dados são carregados
        state.global_feature_importance = None
        print("Dados de fluxo de caixa processados e salvos no estado.")

        # --- Processamento da Aba Contábil ---
        # Posiciona o leitor de volta ao início do arquivo para ler a próxima aba
        await file.seek(0) 
        print("Lendo a aba 'DadosContabeis' do arquivo Excel...")
        df_accounting = pd.read_excel(file.file, sheet_name='DadosContabeis')
        if df_accounting.empty:
            raise HTTPException(status_code=400, detail="A aba 'DadosContabeis' está vazia.")

        cycle_metrics = calcular_prazos_medios(df_accounting, periodo_dias=30)
        state.global_cycle_metrics = cycle_metrics
        print("Prazos médios calculados e salvos no estado.")
        
        return FileUploadResponse(message="Arquivo Excel processado com sucesso!")

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


@router.get("/operational_cycles")
async def get_operational_cycles():
    """Retorna os ciclos operacionais calculados que estão no estado global."""
    if not hasattr(state, 'global_cycle_metrics') or state.global_cycle_metrics is None:
        raise HTTPException(
            status_code=404, 
            detail="Nenhum dado de ciclos operacionais encontrado. Faça o upload do arquivo Excel primeiro."
        )
    
    return JSONResponse(content=state.global_cycle_metrics)


@router.get("/statistics")
async def get_statistics():
    """Retorna as estatísticas históricas calculadas."""
    if state.global_historical_stats is None:
        raise HTTPException(
            status_code=404, 
            detail="Nenhuma estatística calculada. Faça o upload dos dados primeiro."
        )
    
    return JSONResponse(content=state.global_historical_stats)