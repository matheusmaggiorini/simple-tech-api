from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import pandas as pd
import os
import sys
import traceback

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from api.core.deps import get_current_user
from api.endpoints import state
from core.cashflow_predictor import CashflowPredictor

router = APIRouter()


class PredictionRequest(BaseModel):
    future_days: int


def _user_df(user: dict) -> pd.DataFrame | None:
    return state.get_user_session(user["id"]).processed_df


@router.post("/cashflow")
async def predict_cashflow(request: PredictionRequest, user: dict = Depends(get_current_user)):
    """Train the model if needed and return cash-flow forecast for the next days."""
    session = state.get_user_session(user["id"])
    df = session.processed_df

    if df is None or df.empty:
        raise HTTPException(
            status_code=400,
            detail="Nenhum dado foi carregado. Faça o upload de um arquivo primeiro.",
        )

    try:
        if session.prediction_model is None:
            print("Nenhum modelo treinado encontrado. Iniciando treinamento...")
            predictor = CashflowPredictor()
            predictor.train(df)
            session.prediction_model = predictor
            print("Treinamento concluído e modelo salvo na sessão do usuário.")

        future_df = session.prediction_model.predict(request.future_days, df)
        return future_df.to_dict(orient="records")

    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Erro ao gerar a previsão: {e}")


@router.get("/cashflow/feature_importance")
async def get_feature_importance(user: dict = Depends(get_current_user)):
    session = state.get_user_session(user["id"])
    if session.feature_importance is None:
        raise HTTPException(
            status_code=404,
            detail="A análise de importância ainda não foi gerada. Execute a previsão primeiro.",
        )
    return session.feature_importance


@router.get("/cashflow/model_metrics")
async def get_model_metrics(user: dict = Depends(get_current_user)):
    session = state.get_user_session(user["id"])
    if session.model_metrics is None:
        raise HTTPException(
            status_code=404,
            detail="As métricas do modelo ainda não foram geradas. Execute a previsão primeiro.",
        )
    return session.model_metrics
