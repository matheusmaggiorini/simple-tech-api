from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import sys
import os

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Importar o estado compartilhado
from api.endpoints import state

# Definir o router
router = APIRouter()

# Definir os modelos de request/response
class ScenarioParams(BaseModel):
    variacao_entrada: float = 0.10
    variacao_saida: float = 0.10
    dias_simulacao: int = 30
    num_simulacoes: int = 100
    saldo_inicial_simulacao: Optional[float] = None

class ScenarioResponse(BaseModel):
    results_summary: Dict[str, Any]

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
        "data_inicio_simulacao": datetime.now() + timedelta(days=1)
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
    analise["dia_maior_prob_negativo"] = idx_max_prob_negativo.strftime('%Y-%m-%d') if hasattr(idx_max_prob_negativo, 'strftime') else str(idx_max_prob_negativo)
    analise["valor_maior_prob_negativo"] = float(df_resultados["prob_saldo_negativo"].max())
    
    # Valores esperados
    analise["valor_minimo_esperado"] = float(df_resultados["percentil_5"].iloc[-1])
    analise["valor_maximo_esperado"] = float(df_resultados["percentil_95"].iloc[-1])
    analise["valor_mediano_esperado"] = float(df_resultados["percentil_50"].iloc[-1])
    
    return analise

@router.post("/scenarios", response_model=ScenarioResponse)
async def simulate_scenarios(params: ScenarioParams):
    """Executa simulação de Monte Carlo baseada nos dados históricos carregados."""
    # Verificar se os dados necessários estão disponíveis
    if state.global_processed_df is None or state.global_historical_stats is None:
        raise HTTPException(
            status_code=400, 
            detail="Dados não carregados ou estatísticas não calculadas. Faça upload de um arquivo Excel primeiro."
        )

    try:
        # Log dos parâmetros recebidos
        print(f"Parâmetros da simulação recebidos: {params.dict()}")
        
        # Gerar parâmetros para simulação
        parametros_sim = gerar_parametros_simulacao(
            state.global_historical_stats,
            variacao_entrada=params.variacao_entrada,
            variacao_saida=params.variacao_saida,
            dias_simulacao=params.dias_simulacao,
            num_simulacoes=params.num_simulacoes,
            saldo_inicial=params.saldo_inicial_simulacao
        )
        
        print(f"Parâmetros gerados para simulação: {list(parametros_sim.keys())}")
        
        # Executar simulação
        df_resultados_sim, _ = executar_simulacao_monte_carlo(parametros_sim)
        
        # Analisar probabilidades dos resultados da simulação
        analise_prob = analisar_probabilidades(df_resultados_sim)
        
        print(f"Análise de probabilidades concluída: {analise_prob}")
        
        return ScenarioResponse(results_summary=analise_prob)
        
    except Exception as e:
        import traceback
        print(f"Erro na simulação: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Erro interno ao executar simulação: {str(e)}")

# Endpoint adicional para diagnóstico
@router.get("/status")
async def simulation_status():
    """Retorna o status dos dados necessários para simulação."""
    return {
        "dados_processados_disponiveis": state.global_processed_df is not None,
        "estatisticas_disponiveis": state.global_historical_stats is not None,
        "num_registros": len(state.global_processed_df) if state.global_processed_df is not None else 0,
        "estatisticas_chave": state.global_historical_stats if state.global_historical_stats is not None else {}
    }