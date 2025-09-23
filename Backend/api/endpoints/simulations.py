from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, validator
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List
import sys
import os
import traceback
import logging

# Configurar logging para debug
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        simulation_type = values.get('simulation_type', 'macroeconomic')
        
        # Só valida se for simulação macroeconômica
        if simulation_type == 'macroeconomic':
            if not v:
                raise ValueError('scenario_type é obrigatório para a simulação macroeconômica.')
            if v not in ['otimista', 'conservador', 'pessimista']:
                raise ValueError(f'Tipo de cenário inválido: {v}. Use otimista, conservador ou pessimista.')
        
        return v

class SimulationResponse(BaseModel):
    """Modelo para resposta da simulação."""
    scenario_type: str
    original_summary: Dict[str, Any]
    simulated_summary: Dict[str, Any]
    monthly_details: List[Dict[str, Any]]

# --- Funções Auxiliares ---

def calculate_dataframe_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """Calcula um resumo estatístico do DataFrame de previsão."""
    try:
        # Garante que as colunas existam e sejam numéricas
        required_columns = ['receita_total', 'custo_total', 'fluxo_de_caixa']
        for col in required_columns:
            if col not in df.columns:
                df[col] = 0.0
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        summary = {
            "total_receita": float(df['receita_total'].sum()),
            "total_custo": float(df['custo_total'].sum()),
            "total_fluxo_de_caixa": float(df['fluxo_de_caixa'].sum()),
            "meses_com_fluxo_positivo": int((df['fluxo_de_caixa'] > 0).sum()),
            "meses_com_fluxo_negativo": int((df['fluxo_de_caixa'] < 0).sum()),
            # Campos adicionais esperados pelo frontend
            "media_mensal_fluxo": float(df['fluxo_de_caixa'].mean()) if len(df) > 0 else 0.0,
            "menor_fluxo_mensal": float(df['fluxo_de_caixa'].min()) if len(df) > 0 else 0.0,
            "maior_fluxo_mensal": float(df['fluxo_de_caixa'].max()) if len(df) > 0 else 0.0,
        }
        return summary
    except Exception as e:
        logger.error(f"Erro ao calcular resumo do DataFrame: {str(e)}")
        # Retorna resumo padrão em caso de erro
        return {
            "total_receita": 0.0,
            "total_custo": 0.0,
            "total_fluxo_de_caixa": 0.0,
            "meses_com_fluxo_positivo": 0,
            "meses_com_fluxo_negativo": 0,
            "media_mensal_fluxo": 0.0,
            "menor_fluxo_mensal": 0.0,
            "maior_fluxo_mensal": 0.0,
        }

def convert_dataframe_to_monthly_details(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Converte o DataFrame em uma lista de detalhes mensais para o frontend."""
    try:
        df_copy = df.copy()
        # Garante que não há valores NaN que causem problemas no JSON
        for col in ['receita_total', 'custo_total', 'fluxo_de_caixa']:
            if col in df_copy.columns:
                df_copy[col] = pd.to_numeric(df_copy[col], errors='coerce').fillna(0)
        
        return df_copy.to_dict(orient="records")
    except Exception as e:
        logger.error(f"Erro ao converter DataFrame para lista: {str(e)}")
        return []

def create_mock_forecast_data(months: int = 12) -> pd.DataFrame:
    """Cria dados de previsão mock para teste quando não há dados reais."""
    logger.info("⚠️  Criando dados mock para demonstração da simulação")
    
    month_names = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 
                   'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
    
    mock_data = []
    for i in range(months):
        month_name = month_names[i % 12]
        base_revenue = 10000 + (i * 1000)  # Crescimento gradual
        base_cost = 8000 + (i * 500)       # Crescimento gradual dos custos
        
        mock_data.append({
            'mes': month_name,
            'receita_total': base_revenue,
            'custo_total': base_cost,
            'fluxo_de_caixa': base_revenue - base_cost
        })
    
    return pd.DataFrame(mock_data)

def create_mock_historical_data(days: int = 180) -> pd.DataFrame:
    """Cria dados históricos mock para simulação de eventos."""
    logger.info("⚠️  Criando dados históricos mock para simulação de eventos")
    
    np.random.seed(42)  # Para resultados consistentes
    
    # Clientes/fornecedores mock
    clientes = ['Cliente A', 'Cliente B', 'Cliente C', 'Vendas Online', 'Produto X']
    fornecedores = ['Fornecedor 1', 'Fornecedor 2', 'Aluguel', 'Salários', 'Energia']
    
    mock_data = []
    start_date = pd.Timestamp.now() - pd.DateOffset(days=days)
    
    for i in range(days):
        current_date = start_date + pd.DateOffset(days=i)
        
        # Simula transações diárias (nem todo dia tem movimento)
        if np.random.random() > 0.3:  # 70% de chance de ter movimento
            
            # Entradas (receitas)
            if np.random.random() > 0.4:  # 60% de chance de entrada
                cliente = np.random.choice(clientes)
                valor_entrada = np.random.uniform(500, 5000)
                mock_data.append({
                    'data': current_date,
                    'descricao': cliente,
                    'categoria': 'Receita',
                    'entrada': valor_entrada,
                    'saida': 0.0,
                    'saldo': 0.0  # Será calculado depois
                })
            
            # Saídas (custos)
            if np.random.random() > 0.5:  # 50% de chance de saída
                fornecedor = np.random.choice(fornecedores)
                valor_saida = np.random.uniform(200, 3000)
                mock_data.append({
                    'data': current_date,
                    'descricao': fornecedor,
                    'categoria': 'Despesa',
                    'entrada': 0.0,
                    'saida': valor_saida,
                    'saldo': 0.0  # Será calculado depois
                })
    
    df = pd.DataFrame(mock_data)
    
    if not df.empty:
        # Calcula o saldo acumulado
        df = df.sort_values('data')
        df['saldo'] = (df['entrada'] - df['saida']).cumsum()
    
    return df

def validate_historical_data_for_events(df: pd.DataFrame) -> bool:
    """Valida se o DataFrame histórico tem as colunas necessárias para simulação de eventos."""
    required_columns = ['data', 'descricao', 'entrada', 'saida']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        raise ValueError(f"DataFrame histórico deve conter as colunas: {', '.join(missing_columns)}")
    
    # Tenta converter a coluna data
    try:
        df['data'] = pd.to_datetime(df['data'])
    except Exception as e:
        raise ValueError(f"Erro ao converter coluna 'data': {str(e)}")
    
    return True

# --- Endpoints da API ---

@router.get("/key-business-events")
async def get_key_business_events():
    """
    Endpoint: Retorna a lista de principais clientes e custos para
    popular a interface de simulação de eventos.
    """
    try:
        # Se não há dados reais, usa dados mock
        if state.global_processed_df is None or state.global_processed_df.empty:
            logger.warning("⚠️  Nenhum dado processado disponível, usando dados mock para eventos de negócio")
            mock_historical_df = create_mock_historical_data(180)
            events = identify_key_business_events(mock_historical_df, top_n=5)
        else:
            events = identify_key_business_events(state.global_processed_df, top_n=5)
        
        return events
        
    except Exception as e:
        logger.error(f"❌ Erro ao analisar eventos de negócio: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao analisar eventos de negócio: {str(e)}")

@router.post("/scenario-simulation", response_model=SimulationResponse)
async def simulate_scenario(request: SimulationRequest):
    """
    Endpoint PRINCIPAL: Executa uma simulação com base no tipo especificado
    ('macroeconomic' ou 'event').
    """
    try:
        logger.info(f"🔄 Recebida requisição de simulação: {request.simulation_type}")
        
        # Validação inicial do tipo de simulação
        if request.simulation_type not in ['macroeconomic', 'event']:
            raise HTTPException(
                status_code=400, 
                detail=f"Tipo de simulação inválido: '{request.simulation_type}'. Use 'macroeconomic' ou 'event'."
            )

        # Para simulação macroeconômica, usa dados mock
        if request.simulation_type == "macroeconomic":
            logger.info(f"🔄 Iniciando simulação MACROECONÔMICA: {request.scenario_type}")
            
            # Cria dados base para comparação
            df_original = create_mock_forecast_data(12)
            
            # Converte regras de sazonalidade para dict se existirem
            seasonality_dict = []
            if request.seasonality_rules:
                seasonality_dict = [rule.dict() for rule in request.seasonality_rules]
            
            # Executa a simulação
            df_simulated = run_simulation(
                forecast_df=df_original.copy(),
                scenario_type=request.scenario_type,
                seasonality_rules=seasonality_dict
            )
            scenario_name = request.scenario_type

        # Para simulação de eventos, precisa dos dados históricos
        elif request.simulation_type == "event":
            logger.info("🔄 Iniciando simulação de EVENTOS DE NEGÓCIO")
            
            # Verifica se há dados históricos, se não houver, cria dados mock
            if state.global_processed_df is None or state.global_processed_df.empty:
                logger.warning("⚠️  Nenhum dado histórico encontrado, usando dados mock para demonstração")
                historical_df = create_mock_historical_data(180)
            else:
                historical_df = state.global_processed_df.copy()
                
            # Valida os dados históricos
            validate_historical_data_for_events(historical_df)
            
            # Converte modificadores para dict
            inflow_mods = [mod.dict() for mod in request.inflow_modifiers or []]
            outflow_mods = [mod.dict() for mod in request.outflow_modifiers or []]
            
            # Executa a simulação de eventos
            df_simulated_monthly = run_event_simulation(
                historical_df=historical_df,
                inflow_modifiers=inflow_mods,
                outflow_modifiers=outflow_mods
            )
            
            # Debug: Vamos ver que colunas estão disponíveis
            logger.info(f"Colunas disponíveis no resultado da simulação: {list(df_simulated_monthly.columns)}")
            
            # Mapeia as colunas corretamente baseado no que está disponível
            if 'entrada' in df_simulated_monthly.columns:
                receita_col = 'entrada'
                custo_col = 'saida'
                fluxo_col = 'fluxo_diario'
            elif 'receita_total' in df_simulated_monthly.columns:
                receita_col = 'receita_total'
                custo_col = 'custo_total'
                fluxo_col = 'fluxo_de_caixa'
            else:
                # Se não encontra as colunas esperadas, cria valores padrão
                logger.warning("⚠️ Colunas esperadas não encontradas, criando estrutura padrão")
                df_simulated_monthly['entrada'] = 0
                df_simulated_monthly['saida'] = 0
                df_simulated_monthly['fluxo_diario'] = 0
                receita_col = 'entrada'
                custo_col = 'saida'
                fluxo_col = 'fluxo_diario'
            
            # Adapta o resultado para o formato de resposta padrão
            df_simulated = pd.DataFrame({
                "mes": df_simulated_monthly['mes'] if 'mes' in df_simulated_monthly.columns else [f"Mês {i+1}" for i in range(len(df_simulated_monthly))],
                "receita_total": df_simulated_monthly[receita_col],
                "custo_total": df_simulated_monthly[custo_col],
                "fluxo_de_caixa": df_simulated_monthly[fluxo_col]
            })
            
            # Para eventos, usa dados históricos como baseline
            df_original = create_mock_forecast_data(len(df_simulated))
            scenario_name = "event-based"

        # Calcula os resumos e detalhes para a resposta
        logger.info("✅ Simulação executada com sucesso. Calculando resumos...")
        
        original_summary = calculate_dataframe_summary(df_original)
        simulated_summary = calculate_dataframe_summary(df_simulated)
        monthly_details = convert_dataframe_to_monthly_details(df_simulated)

        response = SimulationResponse(
            scenario_type=scenario_name,
            original_summary=original_summary,
            simulated_summary=simulated_summary,
            monthly_details=monthly_details
        )
        
        logger.info(f"✅ Simulação {request.simulation_type} concluída com sucesso")
        return response
        
    except HTTPException as he:
        # Re-raise HTTPException para manter o status code correto
        logger.error(f"❌ HTTPException: {he.detail}")
        raise he
        
    except ValueError as ve:
        logger.error(f"❌ Erro de validação: {str(ve)}")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Erro de validação: {str(ve)}")
        
    except Exception as e:
        logger.error(f"❌ Erro interno na simulação: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro interno ao executar simulação: {str(e)}")

@router.get("/data-availability")
async def check_data_availability():
    """
    Endpoint para verificar se há dados históricos carregados.
    """
    try:
        has_real_data = state.global_processed_df is not None and not state.global_processed_df.empty
        
        if has_real_data:
            data_info = {
                "has_real_data": True,
                "data_source": "uploaded_file",
                "shape": state.global_processed_df.shape,
                "columns": list(state.global_processed_df.columns),
                "date_range": {
                    "start": str(state.global_processed_df['data'].min()) if 'data' in state.global_processed_df.columns else None,
                    "end": str(state.global_processed_df['data'].max()) if 'data' in state.global_processed_df.columns else None
                }
            }
        else:
            data_info = {
                "has_real_data": False,
                "data_source": "mock_data_will_be_used",
                "message": "Nenhum arquivo foi carregado. Dados mock serão usados para demonstração."
            }
        
        return data_info
        
    except Exception as e:
        logger.error(f"❌ Erro ao verificar disponibilidade dos dados: {str(e)}")
        return {
            "has_real_data": False,
            "error": str(e)
        }

@router.get("/status")
async def get_simulation_status():
    """Endpoint para verificar o status do módulo de simulação."""
    try:
        has_data = state.global_processed_df is not None and not state.global_processed_df.empty
        
        status_info = {
            "module": "simulations",
            "status": "active",
            "has_data": has_data,
            "available_scenarios": ["otimista", "conservador", "pessimista"],
            "features": ["macroeconomic_simulation", "event_simulation"]
        }
        
        if has_data:
            status_info["data_shape"] = state.global_processed_df.shape
            status_info["data_columns"] = list(state.global_processed_df.columns)
        
        return status_info
        
    except Exception as e:
        logger.error(f"❌ Erro ao verificar status: {str(e)}")
        return {
            "module": "simulations",
            "status": "error",
            "error": str(e),
            "has_data": False
        }