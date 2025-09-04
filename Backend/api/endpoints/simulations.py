from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, validator
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import sys
import os
import traceback

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Importar o estado compartilhado e o simulador de cenários
from api.endpoints import state
from core.scenario_simulator import run_simulation

# Definir o router
router = APIRouter()

# Definir os modelos de request/response
class SeasonalityRule(BaseModel):
    """Modelo para regras de sazonalidade."""
    month: str
    revenue_change_percentage: float
    
    @validator('month')
    def validate_month(cls, v):
        """Valida se o mês está no formato correto."""
        valid_months = [
            'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
            'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
        ]
        if v not in valid_months:
            raise ValueError(f'Mês deve ser um dos seguintes: {", ".join(valid_months)}')
        return v

class SimulationRequest(BaseModel):
    """Modelo para requisição de simulação de cenários."""
    scenario_type: str
    seasonality_rules: Optional[List[SeasonalityRule]] = None
    
    @validator('scenario_type')
    def validate_scenario_type(cls, v):
        """Valida se o tipo de cenário é válido."""
        valid_scenarios = ['otimista', 'conservador', 'pessimista']
        if v not in valid_scenarios:
            raise ValueError(f'Tipo de cenário deve ser um dos seguintes: {", ".join(valid_scenarios)}')
        return v

class SimulationResponse(BaseModel):
    """Modelo para resposta da simulação."""
    scenario_type: str
    original_summary: Dict[str, Any]
    simulated_summary: Dict[str, Any]
    monthly_details: List[Dict[str, Any]]
    seasonality_applied: bool
    seasonality_rules_count: int

# Cenários macroeconômicos predefinidos (mantido para compatibilidade)
class ScenarioParams(BaseModel):
    variacao_entrada: float = 0.10
    variacao_saida: float = 0.10
    dias_simulacao: int = 30
    num_simulacoes: int = 100
    saldo_inicial_simulacao: Optional[float] = None

class ScenarioResponse(BaseModel):
    results_summary: Dict[str, Any]

def calculate_dataframe_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """Calcula um resumo estatístico do DataFrame de previsão."""
    try:
        summary = {
            "total_receita": float(df['receita_total'].sum()),
            "total_custo": float(df['custo_total'].sum()),
            "total_fluxo_de_caixa": float(df['fluxo_de_caixa'].sum()),
            "media_mensal_receita": float(df['receita_total'].mean()),
            "media_mensal_custo": float(df['custo_total'].mean()),
            "media_mensal_fluxo": float(df['fluxo_de_caixa'].mean()),
            "meses_com_fluxo_positivo": int((df['fluxo_de_caixa'] > 0).sum()),
            "meses_com_fluxo_negativo": int((df['fluxo_de_caixa'] < 0).sum()),
            "maior_receita_mensal": float(df['receita_total'].max()),
            "menor_receita_mensal": float(df['receita_total'].min()),
            "maior_fluxo_mensal": float(df['fluxo_de_caixa'].max()),
            "menor_fluxo_mensal": float(df['fluxo_de_caixa'].min())
        }
        return summary
    except Exception as e:
        print(f"Erro ao calcular resumo do DataFrame: {e}")
        raise

def convert_dataframe_to_monthly_details(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Converte o DataFrame em uma lista de detalhes mensais."""
    try:
        monthly_details = []
        for _, row in df.iterrows():
            month_detail = {
                "mes": str(row['mes']) if 'mes' in row else 'N/A',
                "receita_total": float(row['receita_total']) if pd.notna(row['receita_total']) else 0.0,
                "custo_total": float(row['custo_total']) if pd.notna(row['custo_total']) else 0.0,
                "fluxo_de_caixa": float(row['fluxo_de_caixa']) if pd.notna(row['fluxo_de_caixa']) else 0.0
            }
            monthly_details.append(month_detail)
        return monthly_details
    except Exception as e:
        print(f"Erro ao converter DataFrame para detalhes mensais: {e}")
        raise

def create_mock_forecast_data() -> pd.DataFrame:
    """Cria dados de previsão mock para teste quando não há dados reais."""
    print("⚠️  Criando dados mock para demonstração da simulação")
    mock_data = {
        'mes': ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 
                'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'],
        'receita_total': [10000, 11000, 12000, 13000, 14000, 15000,
                         16000, 17000, 18000, 19000, 20000, 25000],
        'custo_total': [8000, 8500, 9000, 9500, 10000, 10500,
                       11000, 11500, 12000, 12500, 13000, 15000],
        'fluxo_de_caixa': []
    }
    
    # Calcular fluxo de caixa
    for i in range(len(mock_data['receita_total'])):
        fluxo = mock_data['receita_total'][i] - mock_data['custo_total'][i]
        mock_data['fluxo_de_caixa'].append(fluxo)
    
    return pd.DataFrame(mock_data)

@router.post("/scenario-simulation", response_model=SimulationResponse)
async def simulate_scenario(request: SimulationRequest):
    """
    Executa simulação de cenários com base nos parâmetros fornecidos.
    
    Args:
        request: Parâmetros da simulação incluindo tipo de cenário e regras de sazonalidade
        
    Returns:
        SimulationResponse: Resultados da simulação com comparação entre original e simulado
        
    Raises:
        HTTPException: Se ocorrer erro na simulação
    """
    
    try:
        print(f"🔄 Iniciando simulação de cenário: {request.scenario_type}")
        print(f"📊 Regras de sazonalidade: {len(request.seasonality_rules) if request.seasonality_rules else 0}")
        
        # Verificar se temos dados de previsão disponíveis
        df_forecast = None
        
        # Primeira tentativa: usar dados do estado global
        if state.global_processed_df is not None and not state.global_processed_df.empty:
            print("✅ Usando dados do estado global")
            df_forecast = state.global_processed_df.copy()
            
            # Verificar se tem as colunas necessárias, se não, tentar criar
            required_columns = ['mes', 'receita_total', 'custo_total', 'fluxo_de_caixa']
            
            if not all(col in df_forecast.columns for col in required_columns):
                print("⚠️  Dados não possuem formato adequado para simulação")
                # Se não tem as colunas necessárias, usar dados mock
                df_forecast = create_mock_forecast_data()
        else:
            print("⚠️  Nenhum dado encontrado no estado global, usando dados mock")
            df_forecast = create_mock_forecast_data()
        
        print(f"📋 Dataset para simulação: {len(df_forecast)} registros")
        print(f"🏷️  Colunas disponíveis: {list(df_forecast.columns)}")
        
        # Garantir que as colunas necessárias existem
        required_columns = ['mes', 'receita_total', 'custo_total', 'fluxo_de_caixa']
        missing_columns = [col for col in required_columns if col not in df_forecast.columns]
        
        if missing_columns:
            raise HTTPException(
                status_code=400,
                detail=f"Colunas necessárias não encontradas no DataFrame: {', '.join(missing_columns)}"
            )
        
        # Converter regras de sazonalidade para formato adequado
        seasonality_dict = None
        if request.seasonality_rules:
            seasonality_dict = [
                {
                    "month": rule.month,
                    "revenue_change_percentage": rule.revenue_change_percentage
                }
                for rule in request.seasonality_rules
            ]
            print(f"🌐 Aplicando {len(seasonality_dict)} regras de sazonalidade")
        
        # Executar simulação
        print("🚀 Executando simulação...")
        df_original = df_forecast.copy()
        
        df_simulated = run_simulation(
            forecast_df=df_original,
            scenario_type=request.scenario_type,
            seasonality_rules=seasonality_dict
        )
        
        print("✅ Simulação executada com sucesso")
        
        # Calcular resumos
        print("📊 Calculando resumos...")
        original_summary = calculate_dataframe_summary(df_original)
        simulated_summary = calculate_dataframe_summary(df_simulated)
        
        # Converter para detalhes mensais
        print("📝 Preparando detalhes mensais...")
        monthly_details = convert_dataframe_to_monthly_details(df_simulated)
        
        # Preparar resposta
        response = SimulationResponse(
            scenario_type=request.scenario_type,
            original_summary=original_summary,
            simulated_summary=simulated_summary,
            monthly_details=monthly_details,
            seasonality_applied=request.seasonality_rules is not None,
            seasonality_rules_count=len(request.seasonality_rules) if request.seasonality_rules else 0
        )
        
        print("✅ Resposta preparada com sucesso")
        print(f"💰 Receita original: R$ {original_summary['total_receita']:,.2f}")
        print(f"💰 Receita simulada: R$ {simulated_summary['total_receita']:,.2f}")
        print(f"💹 Fluxo original: R$ {original_summary['total_fluxo_de_caixa']:,.2f}")
        print(f"💹 Fluxo simulado: R$ {simulated_summary['total_fluxo_de_caixa']:,.2f}")
        
        return response
        
    except ValueError as ve:
        print(f"❌ Erro de validação: {str(ve)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=400,
            detail=f"Erro de validação: {str(ve)}"
        )
        
    except Exception as e:
        print(f"❌ Erro interno: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno ao executar simulação de cenário: {str(e)}"
        )

# Endpoint de teste para verificar o status
@router.get("/status")
async def get_simulation_status():
    """Endpoint para verificar o status do módulo de simulação."""
    try:
        status_info = {
            "module": "scenarios",
            "status": "active",
            "has_data": state.global_processed_df is not None,
            "data_shape": state.global_processed_df.shape if state.global_processed_df is not None else None,
            "available_scenarios": ["otimista", "conservador", "pessimista"]
        }
        
        return status_info
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao verificar status: {str(e)}"
        )

# Mantendo endpoint legado para compatibilidade
def gerar_parametros_simulacao(
    estatisticas: Dict[str, Any],
    variacao_entrada: float = 0.1,
    variacao_saida: float = 0.1,
    dias_simulacao: int = 30,
    num_simulacoes: int = 1000,
    saldo_inicial: Optional[float] = None,
    seed: Optional[int] = None
) -> Dict[str, Any]:
    """Gera parâmetros para a simulação de Monte Carlo com base nas estatísticas históricas."""
    if seed is not None:
        np.random.seed(seed)
    
    parametros = {
        "dias_simulacao": dias_simulacao,
        "num_simulacoes": num_simulacoes,
        "variacao_entrada": variacao_entrada,
        "variacao_saida": variacao_saida,
        "data_inicio_simulacao": estatisticas.get("ultima_data", datetime.now()) + timedelta(days=1)
    }
    
    # Definir saldo inicial
    if saldo_inicial is not None:
        parametros["saldo_inicial"] = saldo_inicial
    elif "ultimo_saldo" in estatisticas:
        parametros["saldo_inicial"] = estatisticas["ultimo_saldo"]
    else:
        parametros["saldo_inicial"] = 0.0
    
    # Definir parâmetros de distribuição para entradas
    if "media_entrada" in estatisticas:
        parametros["media_entrada_base"] = estatisticas["media_entrada"]
        parametros["media_entrada_min"] = estatisticas["media_entrada"] * (1 - variacao_entrada)
        parametros["media_entrada_max"] = estatisticas["media_entrada"] * (1 + variacao_entrada)
        parametros["desvio_padrao_entrada"] = max(
            estatisticas.get("desvio_padrao_entrada", 0),
            estatisticas["media_entrada"] * 0.05
        )
    
    # Definir parâmetros de distribuição para saídas
    if "media_saida" in estatisticas:
        parametros["media_saida_base"] = estatisticas["media_saida"]
        parametros["media_saida_min"] = estatisticas["media_saida"] * (1 - variacao_saida)
        parametros["media_saida_max"] = estatisticas["media_saida"] * (1 + variacao_saida)
        parametros["desvio_padrao_saida"] = max(
            estatisticas.get("desvio_padrao_saida", 0),
            estatisticas["media_saida"] * 0.05
        )
    
    # Alternativa: usar estatísticas de fluxo diário
    if "media_fluxo" in estatisticas and ("media_entrada_base" not in parametros):
        parametros["media_fluxo_base"] = estatisticas["media_fluxo"]
        parametros["media_fluxo_min"] = estatisticas["media_fluxo"] * (1 - variacao_entrada)
        parametros["media_fluxo_max"] = estatisticas["media_fluxo"] * (1 + variacao_entrada)
        parametros["desvio_padrao_fluxo"] = max(
            estatisticas.get("desvio_padrao_fluxo", 0),
            abs(estatisticas["media_fluxo"]) * 0.05
        )
    
    return parametros

def executar_simulacao_monte_carlo(parametros: Dict[str, Any]) -> tuple:
    """Executa a simulação de Monte Carlo para fluxo de caixa."""
    dias_simulacao = parametros["dias_simulacao"]
    num_simulacoes = parametros["num_simulacoes"]
    saldo_inicial = parametros["saldo_inicial"]
    data_inicio = parametros["data_inicio_simulacao"]
    
    # Criar datas para a simulação
    datas_simulacao = [data_inicio + timedelta(days=i) for i in range(dias_simulacao)]
    
    # Matriz para armazenar resultados
    matriz_saldos = np.zeros((num_simulacoes, dias_simulacao))
    
    # Executar simulações
    for sim in range(num_simulacoes):
        saldo_atual = saldo_inicial
        
        for dia in range(dias_simulacao):
            # Gerar fluxo de caixa para o dia atual
            if "media_entrada_base" in parametros and "media_saida_base" in parametros:
                # Simular entrada e saída separadamente
                media_entrada_sim = np.random.uniform(
                    parametros["media_entrada_min"],
                    parametros["media_entrada_max"]
                )
                media_saida_sim = np.random.uniform(
                    parametros["media_saida_min"],
                    parametros["media_saida_max"]
                )
                
                entrada_dia = max(0, np.random.normal(
                    media_entrada_sim,
                    parametros["desvio_padrao_entrada"]
                ))
                saida_dia = max(0, np.random.normal(
                    media_saida_sim,
                    parametros["desvio_padrao_saida"]
                ))
                
                fluxo_dia = entrada_dia - saida_dia
            
            elif "media_fluxo_base" in parametros:
                # Simular fluxo diário diretamente
                media_fluxo_sim = np.random.uniform(
                    parametros["media_fluxo_min"],
                    parametros["media_fluxo_max"]
                )
                
                fluxo_dia = np.random.normal(
                    media_fluxo_sim,
                    parametros["desvio_padrao_fluxo"]
                )
            else:
                # Fallback: fluxo aleatório simples
                fluxo_dia = np.random.normal(0, 100)
            
            # Atualizar saldo
            saldo_atual += fluxo_dia
            matriz_saldos[sim, dia] = saldo_atual
    
    # Criar DataFrame com resultados agregados
    percentis = [5, 10, 25, 50, 75, 90, 95]
    df_resultados = pd.DataFrame(index=datas_simulacao)
    
    for percentil in percentis:
        df_resultados[f'percentil_{percentil}'] = np.percentile(matriz_saldos, percentil, axis=0)
    
    df_resultados['media'] = np.mean(matriz_saldos, axis=0)
    df_resultados['min'] = np.min(matriz_saldos, axis=0)
    df_resultados['max'] = np.max(matriz_saldos, axis=0)
    
    # Calcular probabilidade de saldo negativo
    prob_saldo_negativo = np.mean(matriz_saldos < 0, axis=0)
    df_resultados['prob_saldo_negativo'] = prob_saldo_negativo
    
    # DataFrame com simulações individuais
    df_simulacoes = pd.DataFrame(
        matriz_saldos.T,
        index=datas_simulacao,
        columns=[f'sim_{i+1}' for i in range(num_simulacoes)]
    )
    
    return df_resultados, df_simulacoes

def analisar_probabilidades(df_resultados: pd.DataFrame) -> Dict[str, Any]:
    """Analisa as probabilidades de eventos específicos."""
    analise = {}
    
    # Probabilidade de saldo negativo no final do período
    analise["prob_saldo_negativo_final"] = float(df_resultados["prob_saldo_negativo"].iloc[-1])
    
    # Probabilidade de saldo negativo em qualquer momento
    analise["prob_saldo_negativo_qualquer_momento"] = float(df_resultados["prob_saldo_negativo"].max())
    
    # Dia com maior probabilidade de saldo negativo
    idx_max_prob_negativo = df_resultados["prob_saldo_negativo"].idxmax()
    analise["dia_maior_prob_negativo"] = idx_max_prob_negativo.strftime('%Y-%m-%d')
    analise["valor_maior_prob_negativo"] = float(df_resultados["prob_saldo_negativo"].max())
    
    # Valores esperados
    analise["valor_minimo_esperado"] = float(df_resultados["percentil_5"].iloc[-1])
    analise["valor_maximo_esperado"] = float(df_resultados["percentil_95"].iloc[-1])
    analise["valor_mediano_esperado"] = float(df_resultados["percentil_50"].iloc[-1])
    
    return analise

@router.post("/scenarios", response_model=ScenarioResponse)
async def simulate_scenarios(params: ScenarioParams):
    """Endpoint legado para simulação de Monte Carlo (mantido para compatibilidade)."""
    if state.global_processed_df is None or state.global_historical_stats is None:
        raise HTTPException(
            status_code=400, 
            detail="Dados não carregados ou estatísticas não calculadas. Faça upload de um arquivo CSV primeiro."
        )

    try:
        # Gerar parâmetros para simulação
        parametros_sim = gerar_parametros_simulacao(
            state.global_historical_stats,
            variacao_entrada=params.variacao_entrada,
            variacao_saida=params.variacao_saida,
            dias_simulacao=params.dias_simulacao,
            num_simulacoes=params.num_simulacoes,
            saldo_inicial=params.saldo_inicial_simulacao
        )
        
        # Executar simulação
        df_resultados_sim, _ = executar_simulacao_monte_carlo(parametros_sim)
        
        # Analisar probabilidades dos resultados da simulação
        analise_prob = analisar_probabilidades(df_resultados_sim)
        
        return ScenarioResponse(results_summary=analise_prob)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno ao executar simulação: {str(e)}")