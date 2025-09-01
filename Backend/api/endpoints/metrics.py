from fastapi import APIRouter, UploadFile, File, HTTPException
import pandas as pd
import os
import sys

# Adiciona o diretório raiz ao path para encontrar os outros módulos
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from core.financial_metrics import calcular_prazos_medios

router = APIRouter()

@router.post("/calculate_operational_cycles")
async def calculate_cycles(file: UploadFile = File(...)):
    """
    Recebe um arquivo CSV com dados contábeis mensais e retorna os prazos médios (PMR, PMP, PME).
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="O arquivo deve ser do tipo CSV.")
    
    try:
        # Lê o arquivo diretamente em um DataFrame do Pandas
        df = pd.read_csv(file.file)
        
        # Assume que cada linha do CSV representa um mês (período de 30 dias)
        resultados = calcular_prazos_medios(df, periodo_dias=30)
        
        return resultados
    
    except ValueError as ve:
        # Captura erros de colunas faltantes e os retorna de forma amigável
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        # Captura outros erros inesperados durante o processamento
        raise HTTPException(status_code=500, detail=f"Ocorreu um erro ao processar o arquivo: {e}")