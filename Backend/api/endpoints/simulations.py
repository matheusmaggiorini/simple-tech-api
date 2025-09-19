from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, validator
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List
import sys
import os
import traceback

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Importar o estado compartilhado e os simuladores de cenários
from api.endpoints import state
# Importa AMBAS as funções de simulação do módulo atualizado
from core.scenario_simulator import run_simulation, run_event_simulation
# Importa a nova função para analisar eventos de negócio
from core.business_event_analyzer import identify_key_business_events

# Definir o router
router = APIRouter()

# --- Modelos Pydantic Atualizados ---

class SeasonalityRule(BaseModel):
    """Modelo para regras de sazonalidade (usado na simulação macro)."""
    month: str
    revenue_change_percentage: float

class EventModifier(BaseModel):
    """Modelo para um modificador de evento de negócio."""
    name: str
    value_change_percentage: float = 0.0
    delay_days: int = 0

class SimulationRequest(BaseModel):
    """Modelo de requisição unificado para ambos os tipos de simulação."""
    simulation_type: str = "macroeconomic"  # 'macroeconomic' ou 'event'
    
    # Parâmetros para simulação macroeconômica
    scenario_type: Optional[str] = None
    seasonality_rules: Optional[List[SeasonalityRule]] = None
    
    # Parâmetros para simulação de eventos
    inflow_modifiers: Optional[List[EventModifier]] = None
    outflow_modifiers: Optional[List[EventModifier]] = None

    @validator('scenario_type', always=True)
    def validate_scenario_type(cls, v, values):
        """Valida se o scenario_type foi fornecido para o tipo de simulação correto."""
        if values.get('simulation_type') == 'macroeconomic' and not v:
            raise ValueError('scenario_type é obrigatório para a simulação macroeconômica.')
        if v and v not in ['otimista', 'conservador', 'pessimista']:
            raise ValueError(f'Tipo de cenário inválido: {v}. Use otimista, conservador ou pessimista.')
        return v

class SimulationResponse(BaseModel):
    """Modelo para resposta da simulação."""
    scenario_type: str
    original_summary: Dict[str, Any]
    simulated_summary: Dict[str, Any]
    monthly_details: List[Dict[str, Any]]

# --- Funções Auxiliares (sem alterações) ---

def calculate_dataframe_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """Calcula um resumo estatístico do DataFrame de previsão."""
    summary = {
        "total_receita": float(df['receita_total'].sum()),
        "total_custo": float(df['custo_total'].sum()),
        "total_fluxo_de_caixa": float(df['fluxo_de_caixa'].sum()),
        "meses_com_fluxo_positivo": int((df['fluxo_de_caixa'] > 0).sum()),
        "meses_com_fluxo_negativo": int((df['fluxo_de_caixa'] < 0).sum()),
        # Campos adicionais esperados pelo frontend
        "media_mensal_fluxo": float(df['fluxo_de_caixa'].mean()),
        "menor_fluxo_mensal": float(df['fluxo_de_caixa'].min()),
        "maior_fluxo_mensal": float(df['fluxo_de_caixa'].max()),
    }
    return summary

def convert_dataframe_to_monthly_details(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Converte o DataFrame em uma lista de detalhes mensais para o frontend."""
    df_copy = df.copy()
    # Garante que não há valores NaN que causem problemas no JSON
    for col in ['receita_total', 'custo_total', 'fluxo_de_caixa']:
        df_copy[col] = df_copy[col].fillna(0)
        
    return df_copy.to_dict(orient="records")

def create_mock_forecast_data(months: int = 12) -> pd.DataFrame:
    """Cria dados de previsão mock para teste quando não há dados reais."""
    print("⚠️  Criando dados mock para demonstração da simulação")
    # (O código desta função permanece o mesmo da sua versão original)
    mock_data = {
        'mes': ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 
                'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'],
        'receita_total': [10000, 11000, 12000, 13000, 14000, 15000,
                         16000, 17000, 18000, 19000, 20000, 25000],
        'custo_total': [8000, 8500, 9000, 9500, 10000, 10500,
                       11000, 11500, 12000, 12500, 13000, 15000],
    }
    df = pd.DataFrame(mock_data)
    df['fluxo_de_caixa'] = df['receita_total'] - df['custo_total']
    return df

# --- Endpoints da API ---

@router.get("/key-business-events")
async def get_key_business_events():
    """
    NOVO endpoint: Retorna a lista de principais clientes e custos para
    popular a interface de simulação de eventos.
    """
    if state.global_processed_df is None or state.global_processed_df.empty:
        raise HTTPException(
            status_code=404,
            detail="Nenhum dado de fluxo de caixa processado. Faça o upload de um arquivo primeiro."
        )
    try:
        events = identify_key_business_events(state.global_processed_df, top_n=5)
        return events
    except Exception as e:
        print(f"❌ Erro ao analisar eventos de negócio: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao analisar eventos de negócio: {str(e)}")

@router.post("/scenario-simulation", response_model=SimulationResponse)
async def simulate_scenario(request: SimulationRequest):
    """
    Endpoint ATUALIZADO: Executa uma simulação com base no tipo especificado
    ('macroeconomic' ou 'event').
    """
    if state.global_processed_df is None or state.global_processed_df.empty:
        raise HTTPException(status_code=400, detail="Dados não carregados. Faça o upload de um arquivo primeiro.")

    try:
        df_original = create_mock_forecast_data() # Usado como base de comparação

        if request.simulation_type == "macroeconomic":
            print(f"🔄 Iniciando simulação MACROECONÔMICA: {request.scenario_type}")
            
            seasonality_dict = [rule.dict() for rule in request.seasonality_rules or []]
            
            df_simulated = run_simulation(
                forecast_df=df_original.copy(),
                scenario_type=request.scenario_type,
                seasonality_rules=seasonality_dict
            )
            scenario_name = request.scenario_type

        elif request.simulation_type == "event":
            print(f"🔄 Iniciando simulação de EVENTOS DE NEGÓCIO")

            df_simulated_monthly = run_event_simulation(
                historical_df=state.global_processed_df,
                inflow_modifiers=[mod.dict() for mod in request.inflow_modifiers or []],
                outflow_modifiers=[mod.dict() for mod in request.outflow_modifiers or []]
            )
            
            # Adapta o resultado para o formato de resposta padrão
            df_simulated = pd.DataFrame({
                "mes": df_simulated_monthly['mes'],
                "receita_total": df_simulated_monthly['entrada'],
                "custo_total": df_simulated_monthly['saida'],
                "fluxo_de_caixa": df_simulated_monthly['fluxo_diario']
            })
            scenario_name = "event-based"

        else:
            raise HTTPException(status_code=400, detail=f"Tipo de simulação inválido: '{request.simulation_type}'")

        # O restante da lógica para preparar a resposta é comum a ambos os tipos
        print("✅ Simulação executada com sucesso. Calculando resumos...")
        original_summary = calculate_dataframe_summary(df_original)
        simulated_summary = calculate_dataframe_summary(df_simulated)
        monthly_details = convert_dataframe_to_monthly_details(df_simulated)

        return SimulationResponse(
            scenario_type=scenario_name,
            original_summary=original_summary,
            simulated_summary=simulated_summary,
            monthly_details=monthly_details
        )
        
    except ValueError as ve:
        print(f"❌ Erro de validação: {str(ve)}")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Erro de validação: {str(ve)}")
        
    except Exception as e:
        print(f"❌ Erro interno na simulação: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro interno ao executar simulação: {str(e)}")

@router.get("/status")
async def get_simulation_status():
    """Endpoint para verificar o status do módulo de simulação."""
    return {
        "module": "simulations",
        "status": "active",
        "has_data": state.global_processed_df is not None and not state.global_processed_df.empty,
        "available_scenarios": ["otimista", "conservador", "pessimista"],
        "features": ["macroeconomic_simulation", "event_simulation"]
    }