# Backend/core/scenario_simulator.py - Versão Corrigida

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
import logging
from datetime import timedelta
from pydantic import BaseModel

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- SEÇÃO 1: SIMULAÇÃO MACROECONÔMICA (CÓDIGO ORIGINAL) ---

MACROECONOMIC_SCENARIOS = {
    "otimista": {
        "revenue_change": 0.15,  # +15%
        "cost_change": -0.10,    # -10%
        "description": "Cenário otimista: aumento de receita e redução de custos"
    },
    "conservador": {
        "revenue_change": 0.05,  # +5%
        "cost_change": 0.03,     # +3%
        "description": "Cenário conservador: crescimento moderado com aumento leve de custos"
    },
    "pessimista": {
        "revenue_change": -0.10, # -10%
        "cost_change": 0.20,     # +20%
        "description": "Cenário pessimista: redução de receita e aumento significativo de custos"
    }
}

def validate_forecast_dataframe(df: pd.DataFrame) -> bool:
    if df is None:
        raise ValueError("DataFrame não pode ser None")
    if df.empty:
        raise ValueError("DataFrame não pode estar vazio")
    required_columns = ['mes', 'receita_total', 'custo_total', 'fluxo_de_caixa']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"DataFrame deve conter as colunas: {', '.join(missing_columns)}")
    return True

def apply_macroeconomic_scenario(df: pd.DataFrame, scenario_type: str) -> pd.DataFrame:
    if scenario_type not in MACROECONOMIC_SCENARIOS:
        raise ValueError(f"Tipo de cenário inválido. Opções válidas: {', '.join(MACROECONOMIC_SCENARIOS.keys())}")
    
    scenario_config = MACROECONOMIC_SCENARIOS[scenario_type]
    df_adjusted = df.copy()
    
    revenue_multiplier = 1 + scenario_config["revenue_change"]
    cost_multiplier = 1 + scenario_config["cost_change"]
    
    df_adjusted['receita_total'] = pd.to_numeric(df_adjusted['receita_total'], errors='coerce').fillna(0) * revenue_multiplier
    df_adjusted['custo_total'] = pd.to_numeric(df_adjusted['custo_total'], errors='coerce').fillna(0) * cost_multiplier
    
    return df_adjusted

def apply_seasonality_adjustments(df: pd.DataFrame, seasonality_rules: List[Dict[str, Any]]) -> pd.DataFrame:
    if not seasonality_rules:
        return df
    df_seasonal = df.copy()
    for rule in seasonality_rules:
        month = rule.get("month", "").strip()
        revenue_change = rule.get("revenue_change_percentage", 0)
        if not month or revenue_change == 0:
            continue
        month_mask = df_seasonal['mes'].str.contains(month, case=False, na=False)
        if month_mask.any():
            df_seasonal.loc[month_mask, 'receita_total'] *= (1 + (revenue_change / 100))
    return df_seasonal

def recalculate_cash_flow(df: pd.DataFrame) -> pd.DataFrame:
    df_recalculated = df.copy()
    df_recalculated['receita_total'] = pd.to_numeric(df_recalculated['receita_total'], errors='coerce').fillna(0)
    df_recalculated['custo_total'] = pd.to_numeric(df_recalculated['custo_total'], errors='coerce').fillna(0)
    df_recalculated['fluxo_de_caixa'] = df_recalculated['receita_total'] - df_recalculated['custo_total']
    return df_recalculated

def run_simulation(forecast_df: pd.DataFrame, scenario_type: str, seasonality_rules: Optional[List[Dict[str, Any]]] = None) -> pd.DataFrame:
    logger.info("INICIANDO SIMULAÇÃO MACROECONÔMICA")
    validate_forecast_dataframe(forecast_df)
    df_simulation = forecast_df.copy()
    df_simulation = apply_macroeconomic_scenario(df_simulation, scenario_type)
    if seasonality_rules:
        df_simulation = apply_seasonality_adjustments(df_simulation, seasonality_rules)
    df_simulation = recalculate_cash_flow(df_simulation)
    logger.info("SIMULAÇÃO MACROECONÔMICA CONCLUÍDA")
    return df_simulation

# --- SEÇÃO 2: SIMULAÇÃO DE EVENTOS DE NEGÓCIO (VERSÃO CORRIGIDA) ---

class EventModifier(BaseModel):
    name: str
    value_change_percentage: float = 0.0
    delay_days: int = 0

def run_event_simulation(
    historical_df: pd.DataFrame, 
    inflow_modifiers: List[Dict[str, Any]], 
    outflow_modifiers: List[Dict[str, Any]], 
    simulation_months: int = 6
) -> pd.DataFrame:
    """
    Versão corrigida da simulação de eventos que garante o retorno das colunas corretas.
    """
    logger.info("INICIANDO SIMULAÇÃO DE EVENTOS DE NEGÓCIO")
    
    try:
        # Valida e prepara os dados
        if historical_df.empty:
            logger.warning("DataFrame histórico vazio, retornando dados mock")
            return create_empty_event_simulation_result(simulation_months)
        
        # Garante que a coluna de data esteja no formato correto
        if 'data' not in historical_df.columns:
            logger.error("Coluna 'data' não encontrada no DataFrame histórico")
            return create_empty_event_simulation_result(simulation_months)
            
        historical_df = historical_df.copy()
        historical_df['data'] = pd.to_datetime(historical_df['data'], errors='coerce')
        
        # Remove linhas com datas inválidas
        historical_df = historical_df.dropna(subset=['data'])
        
        if historical_df.empty:
            logger.warning("Nenhuma data válida encontrada, retornando dados mock")
            return create_empty_event_simulation_result(simulation_months)
        
        # Garante que as colunas necessárias existam
        for col in ['entrada', 'saida']:
            if col not in historical_df.columns:
                historical_df[col] = 0.0
            historical_df[col] = pd.to_numeric(historical_df[col], errors='coerce').fillna(0)
        
        if 'descricao' not in historical_df.columns:
            historical_df['descricao'] = 'Transação'
        
        # Calcula médias mensais baseadas nos dados históricos
        last_date = historical_df['data'].max()
        logger.info(f"Data mais recente nos dados: {last_date}")
        
        # Cria DataFrame para os próximos meses
        future_months = []
        for month_offset in range(1, simulation_months + 1):
            future_date = last_date + pd.DateOffset(months=month_offset)
            future_months.append(future_date)
        
        # Calcula médias históricas por mês
        historical_df['month'] = historical_df['data'].dt.month
        monthly_averages = historical_df.groupby('month').agg({
            'entrada': 'mean',
            'saida': 'mean'
        }).fillna(0)
        
        # Cria as projeções
        simulated_data = []
        for i, future_date in enumerate(future_months):
            month = future_date.month
            
            # Pega a média histórica para esse mês, ou média geral se não houver dados
            if month in monthly_averages.index:
                base_entrada = monthly_averages.loc[month, 'entrada']
                base_saida = monthly_averages.loc[month, 'saida']
            else:
                base_entrada = historical_df['entrada'].mean()
                base_saida = historical_df['saida'].mean()
            
            # Aplica modificadores se existirem
            entrada_modificada = base_entrada
            saida_modificada = base_saida
            
            # Aplica modificadores de entrada
            for modifier in inflow_modifiers:
                change_pct = modifier.get("value_change_percentage", 0) / 100.0
                entrada_modificada *= (1 + change_pct)
            
            # Aplica modificadores de saída
            for modifier in outflow_modifiers:
                change_pct = modifier.get("value_change_percentage", 0) / 100.0
                saida_modificada *= (1 + change_pct)
            
            simulated_data.append({
                'mes': future_date.strftime('%Y-%m'),
                'data': future_date,
                'entrada': max(0, entrada_modificada),
                'saida': max(0, saida_modificada),
                'fluxo_diario': entrada_modificada - saida_modificada
            })
        
        result_df = pd.DataFrame(simulated_data)
        
        # Calcula saldo acumulado
        last_balance = historical_df['saldo'].iloc[-1] if 'saldo' in historical_df.columns and not historical_df.empty else 0
        result_df['saldo_previsto'] = last_balance + result_df['fluxo_diario'].cumsum()
        
        logger.info(f"SIMULAÇÃO CONCLUÍDA - {simulation_months} meses simulados")
        logger.info(f"Colunas no resultado: {list(result_df.columns)}")
        
        return result_df
        
    except Exception as e:
        logger.error(f"Erro na simulação de eventos: {str(e)}")
        logger.exception("Detalhes do erro:")
        return create_empty_event_simulation_result(simulation_months)

def create_empty_event_simulation_result(simulation_months: int = 6) -> pd.DataFrame:
    """
    Cria um resultado vazio mas válido para simulação de eventos.
    """
    logger.warning("Criando resultado vazio para simulação de eventos")
    
    empty_data = []
    current_date = pd.Timestamp.now()
    
    for i in range(simulation_months):
        future_date = current_date + pd.DateOffset(months=i+1)
        empty_data.append({
            'mes': future_date.strftime('%Y-%m'),
            'data': future_date,
            'entrada': 0.0,
            'saida': 0.0,
            'fluxo_diario': 0.0,
            'saldo_previsto': 0.0
        })
    
    return pd.DataFrame(empty_data)

# --- SEÇÃO 3: FUNÇÕES DE APOIO (CÓDIGO ORIGINAL) ---

def generate_scenario_summary(
    original_df: pd.DataFrame, 
    simulated_df: pd.DataFrame, 
    scenario_type: str
) -> Dict[str, Any]:
    """
    Gera um resumo comparativo entre os cenários original e simulado.
    """
    try:
        original_totals = {
            "receita": float(original_df['receita_total'].sum()),
            "custo": float(original_df['custo_total'].sum()),
            "fluxo": float(original_df['fluxo_de_caixa'].sum())
        }
        
        simulated_totals = {
            "receita": float(simulated_df['receita_total'].sum()),
            "custo": float(simulated_df['custo_total'].sum()),
            "fluxo": float(simulated_df['fluxo_de_caixa'].sum())
        }
        
        def safe_percentage_change(new_val, old_val):
            if old_val == 0:
                return 0 if new_val == 0 else 100
            return ((new_val - old_val) / abs(old_val)) * 100
        
        changes = {
            "receita_change": safe_percentage_change(simulated_totals["receita"], original_totals["receita"]),
            "custo_change": safe_percentage_change(simulated_totals["custo"], original_totals["custo"]),
            "fluxo_change": safe_percentage_change(simulated_totals["fluxo"], original_totals["fluxo"])
        }
        
        summary = {
            "scenario_type": scenario_type,
            "scenario_description": MACROECONOMIC_SCENARIOS.get(scenario_type, {}).get("description", ""),
            "original_totals": original_totals,
            "simulated_totals": simulated_totals,
            "percentage_changes": changes,
            "months_analyzed": len(original_df),
            "positive_cash_flow_months_original": int((original_df['fluxo_de_caixa'] > 0).sum()),
            "positive_cash_flow_months_simulated": int((simulated_df['fluxo_de_caixa'] > 0).sum())
        }
        
        return summary
        
    except Exception as e:
        logger.error(f"Erro ao gerar resumo do cenário: {e}")
        raise

def create_sample_forecast_data(months: int = 12) -> pd.DataFrame:
    """
    Cria dados de previsão de exemplo para testes.
    """
    month_names = [
        'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
        'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
    ]
    np.random.seed(42)
    sample_data = []
    base_revenue = 15000
    base_cost = 12000
    for i in range(months):
        month_name = month_names[i % 12]
        seasonal_factor = 1.0
        if month_name in ['Dezembro', 'Janeiro']: seasonal_factor = 1.3
        elif month_name in ['Fevereiro', 'Março']: seasonal_factor = 0.8
        growth_factor = 1 + (i * 0.02)
        noise = np.random.normal(1, 0.1)
        revenue = base_revenue * seasonal_factor * growth_factor * noise
        cost = base_cost * seasonal_factor * growth_factor * np.random.normal(1, 0.05)
        sample_data.append({
            'mes': month_name,
            'receita_total': max(0, revenue),
            'custo_total': max(0, cost),
            'fluxo_de_caixa': revenue - cost
        })
    return pd.DataFrame(sample_data)

# --- SEÇÃO 4: BLOCO DE TESTE ---

if __name__ == "__main__":
    print("=== TESTE DO SIMULADOR DE CENÁRIOS ===")
    
    df_test = create_sample_forecast_data(12)
    
    print("\nDADOS ORIGINAIS:")
    print(df_test[['mes', 'receita_total', 'custo_total', 'fluxo_de_caixa']].round(2))
    
    print(f"\nRESUMO ORIGINAL:")
    print(f"Receita Total: R$ {df_test['receita_total'].sum():,.2f}")
    print(f"Custo Total: R$ {df_test['custo_total'].sum():,.2f}")
    print(f"Fluxo Total: R$ {df_test['fluxo_de_caixa'].sum():,.2f}")
    
    # Teste 1: Cenário otimista simples
    print("\n" + "="*50)
    print("TESTE 1: CENÁRIO OTIMISTA")
    print("="*50)
    
    try:
        df_optimistic = run_simulation(df_test, 'otimista')
        print("\nRESULTADO OTIMISTA:")
        print(f"Receita Total: R$ {df_optimistic['receita_total'].sum():,.2f}")
        print(f"Custo Total: R$ {df_optimistic['custo_total'].sum():,.2f}")
        print(f"Fluxo Total: R$ {df_optimistic['fluxo_de_caixa'].sum():,.2f}")
    except Exception as e:
        print(f"ERRO no teste 1: {e}")
    
    print("\n" + "="*50)
    print("TESTES CONCLUÍDOS")
    print("="*50)