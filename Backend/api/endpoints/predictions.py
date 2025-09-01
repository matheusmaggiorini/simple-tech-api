from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import pandas as pd
import os
import sys
import traceback

# Adiciona o diretório raiz ao path para importações corretas
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from api.endpoints import state
from core.cashflow_predictor import CashflowPredictor

router = APIRouter()

class PredictionRequest(BaseModel):
    future_days: int

@router.post("/cashflow")
async def predict_cashflow(request: PredictionRequest):
    """
    Treina o modelo (se necessário) e retorna a PREVISÃO REAL para os próximos dias.
    """
    if state.global_processed_df is None or state.global_processed_df.empty:
        raise HTTPException(status_code=400, detail="Nenhum dado foi carregado. Faça o upload de um arquivo primeiro.")

    try:
        # Garante que o modelo está treinado com os dados atuais.
        if state.global_prediction_model is None:
            print("Nenhum modelo treinado encontrado. Iniciando treinamento...")
            predictor = CashflowPredictor()
            predictor.train(state.global_processed_df)
            state.global_prediction_model = predictor # Salva o predictor treinado
            print("Treinamento concluído e modelo salvo no estado.")
        
        # --- ESTA É A CORREÇÃO FINAL E DEFINITIVA ---
        # Chama a função de previsão e obtém o DataFrame com os resultados.
        predictor_instance = state.global_prediction_model
        future_df = predictor_instance.predict(request.future_days, state.global_processed_df)
        
        # Converte o DataFrame para um formato de lista de dicionários (JSON Array),
        # que é o que o frontend espera.
        return future_df.to_dict(orient='records')
        # --- FIM DA CORREÇÃO ---

    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Erro ao gerar a previsão: {e}")

@router.get("/cashflow/feature_importance")
async def get_feature_importance():
    """
    Retorna a lista das variáveis mais importantes que o modelo de previsão
    utilizou, ordenadas da mais para a menos importante.
    """
    if state.global_feature_importance is None:
        raise HTTPException(
            status_code=404,
            detail="A análise de importância ainda não foi gerada. Execute a previsão primeiro para treinar o modelo."
        )
    
    return state.global_feature_importance