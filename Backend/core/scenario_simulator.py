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
        "description": "Cenário otimista (percentil 75): aumento de receita e redução de custos"
    },
    "mais_provavel": {
        "revenue_change": 0.05,  # +5%
        "cost_change": 0.03,     # +3%
        "description": "Cenário mais provável (percentil 50): crescimento moderado com aumento leve de custos"
    },
    "pessimista": {
        "revenue_change": -0.10, # -10%
        "cost_change": 0.20,     # +20%
        "description": "Cenário pessimista (percentil 25): redução de receita e aumento significativo de custos"
    },
    # Mantém compatibilidade com nome antigo
    "conservador": {
        "revenue_change": 0.05,  # +5%
        "cost_change": 0.03,     # +3%
        "description": "Cenário mais provável (percentil 50): crescimento moderado com aumento leve de custos"
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
    Versão melhorada da simulação de eventos com projeções mais realistas baseadas em padrões históricos.
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
        
        # Calcula estatísticas históricas mais robustas
        last_date = historical_df['data'].max()
        logger.info(f"Data mais recente nos dados: {last_date}")
        
        # Agrupa por mês para calcular padrões sazonais
        historical_df['year_month'] = historical_df['data'].dt.to_period('M')
        historical_df['month'] = historical_df['data'].dt.month
        
        # Calcula totais mensais (não médias diárias) para ser mais realista
        monthly_totals = historical_df.groupby('year_month').agg({
            'entrada': 'sum',
            'saida': 'sum'
        }).reset_index()
        
        monthly_totals['fluxo'] = monthly_totals['entrada'] - monthly_totals['saida']
        
        # Calcula padrões sazonais por mês (1-12)
        monthly_patterns = historical_df.groupby('month').agg({
            'entrada': ['mean', 'std', 'sum'],
            'saida': ['mean', 'std', 'sum']
        }).fillna(0)
        
        # Médias gerais e desvios padrão
        avg_entrada_mensal = monthly_totals['entrada'].mean() if not monthly_totals.empty else 0
        avg_saida_mensal = monthly_totals['saida'].mean() if not monthly_totals.empty else 0
        std_entrada_mensal = monthly_totals['entrada'].std() if len(monthly_totals) > 1 else avg_entrada_mensal * 0.2
        std_saida_mensal = monthly_totals['saida'].std() if len(monthly_totals) > 1 else avg_saida_mensal * 0.2
        
        # Tendência dos últimos meses (se houver dados suficientes)
        if len(monthly_totals) >= 3:
            recent_totals = monthly_totals.tail(3)
            trend_entrada = (recent_totals['entrada'].iloc[-1] - recent_totals['entrada'].iloc[0]) / len(recent_totals)
            trend_saida = (recent_totals['saida'].iloc[-1] - recent_totals['saida'].iloc[0]) / len(recent_totals)
        else:
            trend_entrada = 0
            trend_saida = 0
        
        # Cria DataFrame para os próximos meses
        future_months = []
        for month_offset in range(1, simulation_months + 1):
            future_date = last_date + pd.DateOffset(months=month_offset)
            future_months.append(future_date)
        
        # Cria as projeções com variação realista
        simulated_data = []
        np.random.seed(42)  # Para resultados reprodutíveis
        
        for i, future_date in enumerate(future_months):
            month = future_date.month
            
            # Base mensal com padrão sazonal
            if month in monthly_patterns.index:
                seasonal_factor_e = monthly_patterns.loc[month, ('entrada', 'mean')] / avg_entrada_mensal if avg_entrada_mensal > 0 else 1.0
                seasonal_factor_s = monthly_patterns.loc[month, ('saida', 'mean')] / avg_saida_mensal if avg_saida_mensal > 0 else 1.0
            else:
                seasonal_factor_e = 1.0
                seasonal_factor_s = 1.0
            
            # Projeção base com sazonalidade e tendência
            base_entrada = (avg_entrada_mensal * seasonal_factor_e) + (trend_entrada * (i + 1))
            base_saida = (avg_saida_mensal * seasonal_factor_s) + (trend_saida * (i + 1))
            
            # Adiciona variação realista (20% do desvio padrão, limitada)
            variation_factor_e = np.random.normal(0, min(0.2, std_entrada_mensal / max(avg_entrada_mensal, 1)))
            variation_factor_s = np.random.normal(0, min(0.2, std_saida_mensal / max(avg_saida_mensal, 1)))
            
            entrada_projecao = base_entrada * (1 + variation_factor_e)
            saida_projecao = base_saida * (1 + variation_factor_s)
            
            # Aplica modificadores de eventos se existirem
            entrada_modificada = entrada_projecao
            saida_modificada = saida_projecao
            
            for modifier in inflow_modifiers:
                change_pct = modifier.get("value_change_percentage", 0) / 100.0
                delay = modifier.get("delay_days", 0)
                # Aplica apenas se já passou o delay (meses)
                if (i + 1) * 30 >= delay:
                    entrada_modificada *= (1 + change_pct)
            
            for modifier in outflow_modifiers:
                change_pct = modifier.get("value_change_percentage", 0) / 100.0
                delay = modifier.get("delay_days", 0)
                if (i + 1) * 30 >= delay:
                    saida_modificada *= (1 + change_pct)
            
            # Garante valores não negativos e realistas
            entrada_final = max(0, entrada_modificada)
            saida_final = max(0, saida_modificada)
            
            simulated_data.append({
                'mes': future_date.strftime('%Y-%m'),
                'data': future_date,
                'entrada': entrada_final,
                'saida': saida_final,
                'fluxo_diario': entrada_final - saida_final
            })
        
        result_df = pd.DataFrame(simulated_data)
        
        # Calcula saldo acumulado
        last_balance = historical_df['saldo'].iloc[-1] if 'saldo' in historical_df.columns and not historical_df.empty else 0
        result_df['saldo_previsto'] = last_balance + result_df['fluxo_diario'].cumsum()
        
        logger.info(f"SIMULAÇÃO CONCLUÍDA - {simulation_months} meses simulados")
        logger.info(f"Colunas no resultado: {list(result_df.columns)}")
        logger.info(f"Entrada média projetada: R$ {result_df['entrada'].mean():,.2f}")
        logger.info(f"Saída média projetada: R$ {result_df['saida'].mean():,.2f}")
        
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

# --- Função de Simulação de Empréstimo ---
def run_loan_simulation(
    historical_df: pd.DataFrame,
    amount: float,
    interest_rate_monthly: float,
    term_months: int,
    simulation_months: int = 12
) -> pd.DataFrame:
    """
    Executa uma simulação de fluxo de caixa injetando um empréstimo.
    """
    # 1. Projeta o fluxo de caixa base (sem o empréstimo)
    base_simulation = run_event_simulation(historical_df, [], [], simulation_months)
    
    # Converte o 'mes' para datetime para facilitar a manipulação
    base_simulation['data'] = pd.to_datetime(base_simulation['mes'])
    base_simulation.set_index('data', inplace=True)

    # 2. Calcula a parcela do empréstimo (Tabela Price)
    if interest_rate_monthly > 0:
        rate = interest_rate_monthly / 100
        installment = (amount * rate) / (1 - (1 + rate)**-term_months)
    else:
        installment = amount / term_months if term_months > 0 else 0

    # 3. Injeta o empréstimo na simulação
    # Adiciona o valor do empréstimo como entrada no primeiro dia
    if not base_simulation.empty:
        first_day = base_simulation.index[0]
        if 'entrada' not in base_simulation.columns:
            base_simulation['entrada'] = 0.0
        if 'saida' not in base_simulation.columns:
            base_simulation['saida'] = 0.0
        base_simulation.loc[first_day, 'entrada'] += amount

        # Adiciona a parcela como saída recorrente
        for i in range(min(term_months, simulation_months)):
            target_month = base_simulation.index[i]
            base_simulation.loc[target_month, 'saida'] += installment
    
    # 4. Recalcula o fluxo e o saldo
    base_simulation['fluxo_diario'] = base_simulation.get('entrada', 0) - base_simulation.get('saida', 0)
    last_balance = historical_df['saldo'].iloc[-1] if 'saldo' in historical_df.columns and not historical_df.empty else 0
    base_simulation['saldo_previsto'] = last_balance + base_simulation['fluxo_diario'].cumsum()
    
    base_simulation.reset_index(inplace=True)
    base_simulation['mes'] = base_simulation['data'].dt.strftime('%Y-%m')
    
    return base_simulation

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