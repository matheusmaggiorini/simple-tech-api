# Backend/core/scenario_simulator.py - Versão Final, Completa e Corrigida

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

# --- SEÇÃO 2: SIMULAÇÃO DE EVENTOS DE NEGÓCIO (NOVO CÓDIGO) ---

class EventModifier(BaseModel):
    name: str
    value_change_percentage: float = 0.0
    delay_days: int = 0

def run_event_simulation(historical_df: pd.DataFrame, inflow_modifiers: List[Dict[str, Any]], outflow_modifiers: List[Dict[str, Any]], simulation_months: int = 6) -> pd.DataFrame:
    logger.info("INICIANDO SIMULAÇÃO DE EVENTOS DE NEGÓCIO")
    
    # Garante que a coluna de data esteja no formato correto
    historical_df['data'] = pd.to_datetime(historical_df['data'])
    
    last_date = historical_df['data'].max()
    future_dates = pd.date_range(start=last_date + timedelta(days=1), periods=simulation_months * 30, freq='D')
    simulated_df = pd.DataFrame(index=future_dates, data={'entrada': 0.0, 'saida': 0.0})

    avg_transactions = historical_df.groupby([historical_df['data'].dt.day, 'descricao']).agg({'entrada': 'mean', 'saida': 'mean'}).reset_index().rename(columns={'data': 'day_of_month'})

    for month_offset in range(1, simulation_months + 1):
        for _, row in avg_transactions.iterrows():
            try:
                # Constrói a data alvo no futuro
                target_date = (last_date + pd.DateOffset(months=month_offset)).replace(day=row['day_of_month'])
                if target_date in simulated_df.index:
                    simulated_df.loc[target_date, 'entrada'] += row['entrada']
                    simulated_df.loc[target_date, 'saida'] += row['saida']
            except ValueError:
                # Lida com dias que não existem em certos meses (ex: dia 31 em Fev)
                try:
                    base_date = last_date + pd.DateOffset(months=month_offset)
                    last_day_of_month = base_date.days_in_month
                    if row['day_of_month'] > last_day_of_month:
                         target_date = base_date.replace(day=last_day_of_month)
                         if target_date in simulated_df.index:
                            simulated_df.loc[target_date, 'entrada'] += row['entrada']
                            simulated_df.loc[target_date, 'saida'] += row['saida']
                except Exception:
                    continue
    
    all_modifiers = inflow_modifiers + outflow_modifiers
    for modifier in all_modifiers:
        mod_name = modifier.get("name")
        value_change = modifier.get("value_change_percentage", 0) / 100.0
        delay = timedelta(days=modifier.get("delay_days", 0))

        events_to_modify = avg_transactions[avg_transactions['descricao'] == mod_name]

        for month_offset in range(1, simulation_months + 1):
            for _, event_row in events_to_modify.iterrows():
                try:
                    original_date = (last_date + pd.DateOffset(months=month_offset)).replace(day=event_row['day_of_month'])
                    modified_date = original_date + delay

                    if original_date in simulated_df.index:
                        if event_row['entrada'] > 0:
                            original_value = event_row['entrada']
                            simulated_df.loc[original_date, 'entrada'] -= original_value
                            if modified_date in simulated_df.index:
                                simulated_df.loc[modified_date, 'entrada'] += original_value * (1 + value_change)
                        
                        elif event_row['saida'] > 0:
                            original_value = event_row['saida']
                            simulated_df.loc[original_date, 'saida'] -= original_value
                            if modified_date in simulated_df.index:
                                simulated_df.loc[modified_date, 'saida'] += original_value * (1 + value_change)
                except ValueError:
                    continue

    simulated_df['fluxo_diario'] = simulated_df['entrada'] - simulated_df['saida']
    last_balance = historical_df['saldo'].iloc[-1] if 'saldo' in historical_df.columns and not historical_df.empty else 0
    simulated_df['saldo_previsto'] = last_balance + simulated_df['fluxo_diario'].cumsum()

    monthly_summary = simulated_df.resample('M').agg({'entrada': 'sum', 'saida': 'sum', 'fluxo_diario': 'sum', 'saldo_previsto': 'last'}).reset_index()
    monthly_summary.rename(columns={'index': 'data'}, inplace=True)
    monthly_summary['mes'] = monthly_summary['data'].dt.strftime('%Y-%m')
    
    logger.info("SIMULAÇÃO DE EVENTOS DE NEGÓCIO CONCLUÍDA")
    return monthly_summary

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
    
    # Teste 2: Cenário pessimista com sazonalidade
    print("\n" + "="*50)
    print("TESTE 2: CENÁRIO PESSIMISTA COM SAZONALIDADE")
    print("="*50)
    
    seasonality_rules = [
        {"month": "Dezembro", "revenue_change_percentage": 25},
        {"month": "Janeiro", "revenue_change_percentage": -20},
        {"month": "Fevereiro", "revenue_change_percentage": -15}
    ]
    
    try:
        df_pessimistic = run_simulation(
            df_test, 
            'pessimista', 
            seasonality_rules
        )
        
        print("\nRESULTADO PESSIMISTA + SAZONALIDADE:")
        print(f"Receita Total: R$ {df_pessimistic['receita_total'].sum():,.2f}")
        print(f"Custo Total: R$ {df_pessimistic['custo_total'].sum():,.2f}")
        print(f"Fluxo Total: R$ {df_pessimistic['fluxo_de_caixa'].sum():,.2f}")
        
        summary = generate_scenario_summary(df_test, df_pessimistic, 'pessimista')
        print(f"\nCOMPARAÇÃO:")
        print(f"Mudança na Receita: {summary['percentage_changes']['receita_change']:+.1f}%")
        print(f"Mudança no Custo: {summary['percentage_changes']['custo_change']:+.1f}%")
        print(f"Mudança no Fluxo: {summary['percentage_changes']['fluxo_change']:+.1f}%")
        
    except Exception as e:
        print(f"ERRO no teste 2: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*50)
    print("TESTES CONCLUÍDOS")
    print("="*50)