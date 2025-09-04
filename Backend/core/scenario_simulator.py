# Backend/core/scenario_simulator.py - Versão Corrigida

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
import logging
from datetime import datetime, timedelta

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cenários macroeconômicos predefinidos
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
    """
    Valida se o DataFrame possui as colunas necessárias para simulação.
    
    Args:
        df: DataFrame com dados de previsão
        
    Returns:
        bool: True se válido, False caso contrário
        
    Raises:
        ValueError: Se o DataFrame não possuir as colunas necessárias
    """
    if df is None:
        raise ValueError("DataFrame não pode ser None")
        
    if df.empty:
        raise ValueError("DataFrame não pode estar vazio")
    
    required_columns = ['mes', 'receita_total', 'custo_total', 'fluxo_de_caixa']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        # Log das colunas disponíveis para debug
        logger.warning(f"Colunas disponíveis no DataFrame: {list(df.columns)}")
        logger.warning(f"Colunas faltantes: {missing_columns}")
        raise ValueError(f"DataFrame deve conter as colunas: {', '.join(missing_columns)}")
    
    # Verificar se há dados válidos
    if len(df) == 0:
        raise ValueError("DataFrame não contém nenhum registro")
    
    # Verificar se as colunas numéricas contêm valores válidos
    numeric_columns = ['receita_total', 'custo_total', 'fluxo_de_caixa']
    for col in numeric_columns:
        if df[col].isna().all():
            raise ValueError(f"Coluna {col} contém apenas valores NaN")
    
    logger.info(f"DataFrame validado com sucesso: {len(df)} registros, colunas: {list(df.columns)}")
    return True

def apply_macroeconomic_scenario(df: pd.DataFrame, scenario_type: str) -> pd.DataFrame:
    """
    Aplica ajustes macroeconômicos predefinidos ao DataFrame de previsão.
    
    Args:
        df: DataFrame com dados de previsão
        scenario_type: Tipo do cenário ('otimista', 'conservador', 'pessimista')
        
    Returns:
        pd.DataFrame: DataFrame com ajustes aplicados
        
    Raises:
        ValueError: Se o tipo de cenário não for válido
    """
    if scenario_type not in MACROECONOMIC_SCENARIOS:
        valid_scenarios = ', '.join(MACROECONOMIC_SCENARIOS.keys())
        raise ValueError(f"Tipo de cenário inválido. Opções válidas: {valid_scenarios}")
    
    scenario_config = MACROECONOMIC_SCENARIOS[scenario_type]
    df_adjusted = df.copy()
    
    # Aplicar mudanças percentuais
    revenue_multiplier = 1 + scenario_config["revenue_change"]
    cost_multiplier = 1 + scenario_config["cost_change"]
    
    logger.info(f"Aplicando cenário {scenario_type}:")
    logger.info(f"  Receita: {scenario_config['revenue_change']:+.1%} (multiplicador: {revenue_multiplier:.3f})")
    logger.info(f"  Custo: {scenario_config['cost_change']:+.1%} (multiplicador: {cost_multiplier:.3f})")
    
    # Garantir que os valores sejam numéricos
    df_adjusted['receita_total'] = pd.to_numeric(df_adjusted['receita_total'], errors='coerce').fillna(0)
    df_adjusted['custo_total'] = pd.to_numeric(df_adjusted['custo_total'], errors='coerce').fillna(0)
    
    # Aplicar ajustes
    df_adjusted['receita_total'] = df_adjusted['receita_total'] * revenue_multiplier
    df_adjusted['custo_total'] = df_adjusted['custo_total'] * cost_multiplier
    
    # Log dos valores antes e depois para debug
    logger.info(f"Receita total antes: R$ {df['receita_total'].sum():,.2f}")
    logger.info(f"Receita total depois: R$ {df_adjusted['receita_total'].sum():,.2f}")
    logger.info(f"Custo total antes: R$ {df['custo_total'].sum():,.2f}")
    logger.info(f"Custo total depois: R$ {df_adjusted['custo_total'].sum():,.2f}")
    
    return df_adjusted

def apply_seasonality_adjustments(df: pd.DataFrame, seasonality_rules: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Aplica ajustes de sazonalidade específicos por mês ao DataFrame.
    
    Args:
        df: DataFrame com dados de previsão já ajustados pelo cenário macroeconômico
        seasonality_rules: Lista de regras de sazonalidade
            Formato: [{"month": "Dezembro", "revenue_change_percentage": 30}]
            
    Returns:
        pd.DataFrame: DataFrame com ajustes de sazonalidade aplicados
    """
    if not seasonality_rules:
        return df
        
    df_seasonal = df.copy()
    
    logger.info(f"Aplicando {len(seasonality_rules)} regras de sazonalidade")
    
    for i, rule in enumerate(seasonality_rules):
        try:
            month = rule.get("month", "").strip()
            revenue_change = rule.get("revenue_change_percentage", 0)
            
            if not month:
                logger.warning(f"Regra {i+1}: mês não especificado, ignorando")
                continue
                
            if revenue_change == 0:
                logger.info(f"Regra {i+1}: sem mudança para {month}, ignorando")
                continue
            
            # Procurar registros do mês (busca flexível)
            month_mask = df_seasonal['mes'].str.contains(month, case=False, na=False)
            matching_rows = df_seasonal[month_mask]
            
            if matching_rows.empty:
                # Tentar busca mais flexível
                month_partial_mask = df_seasonal['mes'].str.lower().str.contains(month.lower()[:3], na=False)
                matching_rows = df_seasonal[month_partial_mask]
                
                if matching_rows.empty:
                    logger.warning(f"Regra {i+1}: nenhum registro encontrado para '{month}' no dataset")
                    logger.info(f"Meses disponíveis: {list(df_seasonal['mes'].unique())}")
                    continue
                else:
                    month_mask = month_partial_mask
            
            # Aplicar mudança percentual na receita
            multiplier = 1 + (revenue_change / 100)
            receita_antes = df_seasonal.loc[month_mask, 'receita_total'].sum()
            
            df_seasonal.loc[month_mask, 'receita_total'] *= multiplier
            
            receita_depois = df_seasonal.loc[month_mask, 'receita_total'].sum()
            
            logger.info(f"Regra {i+1} aplicada ao mês '{month}':")
            logger.info(f"  Ajuste: {revenue_change:+.1f}%")
            logger.info(f"  Registros afetados: {len(matching_rows)}")
            logger.info(f"  Receita antes: R$ {receita_antes:,.2f}")
            logger.info(f"  Receita depois: R$ {receita_depois:,.2f}")
            
        except Exception as e:
            logger.error(f"Erro ao aplicar regra de sazonalidade {i+1}: {e}")
            continue
    
    return df_seasonal

def recalculate_cash_flow(df: pd.DataFrame) -> pd.DataFrame:
    """
    Recalcula a coluna de fluxo de caixa após os ajustes.
    
    Args:
        df: DataFrame com receita e custo já ajustados
        
    Returns:
        pd.DataFrame: DataFrame com fluxo de caixa recalculado
    """
    df_recalculated = df.copy()
    
    # Garantir que os valores são numéricos
    df_recalculated['receita_total'] = pd.to_numeric(df_recalculated['receita_total'], errors='coerce').fillna(0)
    df_recalculated['custo_total'] = pd.to_numeric(df_recalculated['custo_total'], errors='coerce').fillna(0)
    
    # Recalcular fluxo de caixa
    df_recalculated['fluxo_de_caixa'] = df_recalculated['receita_total'] - df_recalculated['custo_total']
    
    # Log do resultado
    fluxo_total = df_recalculated['fluxo_de_caixa'].sum()
    meses_positivos = (df_recalculated['fluxo_de_caixa'] > 0).sum()
    meses_negativos = (df_recalculated['fluxo_de_caixa'] < 0).sum()
    
    logger.info("Fluxo de caixa recalculado:")
    logger.info(f"  Total: R$ {fluxo_total:,.2f}")
    logger.info(f"  Meses positivos: {meses_positivos}")
    logger.info(f"  Meses negativos: {meses_negativos}")
    
    return df_recalculated

def run_simulation(
    forecast_df: pd.DataFrame,
    scenario_type: str,
    seasonality_rules: Optional[List[Dict[str, Any]]] = None
) -> pd.DataFrame:
    """
    Executa simulação de cenários aplicando ajustes macroeconômicos e de sazonalidade.
    
    Args:
        forecast_df: DataFrame com previsão base contendo colunas:
                    - mes: Nome do mês
                    - receita_total: Receita total prevista
                    - custo_total: Custo total previsto
                    - fluxo_de_caixa: Fluxo de caixa previsto (receita - custo)
        scenario_type: Tipo de cenário ('otimista', 'conservador', 'pessimista')
        seasonality_rules: Lista opcional de regras de sazonalidade
                          Formato: [{"month": "Dezembro", "revenue_change_percentage": 30}]
                          
    Returns:
        pd.DataFrame: DataFrame simulado com todos os ajustes aplicados
        
    Raises:
        ValueError: Se os parâmetros forem inválidos
    """
    logger.info("="*60)
    logger.info("INICIANDO SIMULAÇÃO DE CENÁRIOS")
    logger.info("="*60)
    logger.info(f"Cenário: {scenario_type}")
    logger.info(f"Regras de sazonalidade: {len(seasonality_rules) if seasonality_rules else 0}")
    
    try:
        # 1. Validar DataFrame de entrada
        validate_forecast_dataframe(forecast_df)
        
        # 2. Criar cópia do DataFrame original
        df_simulation = forecast_df.copy()
        logger.info(f"DataFrame de entrada: {len(df_simulation)} registros")
        
        # Log das estatísticas iniciais
        logger.info("ESTATÍSTICAS INICIAIS:")
        logger.info(f"  Receita total: R$ {df_simulation['receita_total'].sum():,.2f}")
        logger.info(f"  Custo total: R$ {df_simulation['custo_total'].sum():,.2f}")
        logger.info(f"  Fluxo total: R$ {df_simulation['fluxo_de_caixa'].sum():,.2f}")
        
        # 3. Aplicar ajustes de cenário macroeconômico
        logger.info("\n" + "="*40)
        logger.info("APLICANDO CENÁRIO MACROECONÔMICO")
        logger.info("="*40)
        df_simulation = apply_macroeconomic_scenario(df_simulation, scenario_type)
        
        # 4. Aplicar ajustes de sazonalidade (se fornecidos)
        if seasonality_rules and len(seasonality_rules) > 0:
            logger.info("\n" + "="*40)
            logger.info("APLICANDO AJUSTES DE SAZONALIDADE")
            logger.info("="*40)
            df_simulation = apply_seasonality_adjustments(df_simulation, seasonality_rules)
        
        # 5. Recalcular fluxo de caixa
        logger.info("\n" + "="*40)
        logger.info("RECALCULANDO FLUXO DE CAIXA")
        logger.info("="*40)
        df_simulation = recalculate_cash_flow(df_simulation)
        
        # Log das estatísticas finais
        logger.info("\nESTATÍSTICAS FINAIS:")
        logger.info(f"  Receita total: R$ {df_simulation['receita_total'].sum():,.2f}")
        logger.info(f"  Custo total: R$ {df_simulation['custo_total'].sum():,.2f}")
        logger.info(f"  Fluxo total: R$ {df_simulation['fluxo_de_caixa'].sum():,.2f}")
        
        logger.info("="*60)
        logger.info("SIMULAÇÃO CONCLUÍDA COM SUCESSO")
        logger.info("="*60)
        
        return df_simulation
        
    except Exception as e:
        logger.error(f"ERRO NA SIMULAÇÃO: {e}")
        logger.error("="*60)
        raise

def generate_scenario_summary(
    original_df: pd.DataFrame, 
    simulated_df: pd.DataFrame, 
    scenario_type: str
) -> Dict[str, Any]:
    """
    Gera um resumo comparativo entre os cenários original e simulado.
    
    Args:
        original_df: DataFrame original
        simulated_df: DataFrame simulado
        scenario_type: Tipo de cenário aplicado
        
    Returns:
        Dict[str, Any]: Resumo com comparações e métricas
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
        
        # Calcular mudanças percentuais
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

# Função para criar dados de exemplo/teste
def create_sample_forecast_data(months: int = 12) -> pd.DataFrame:
    """
    Cria dados de previsão de exemplo para testes.
    
    Args:
        months: Número de meses para gerar
        
    Returns:
        pd.DataFrame: DataFrame com dados de exemplo
    """
    month_names = [
        'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
        'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
    ]
    
    # Gerar dados com alguma variação sazonal
    np.random.seed(42)  # Para reprodutibilidade
    
    sample_data = []
    base_revenue = 15000
    base_cost = 12000
    
    for i in range(months):
        month_name = month_names[i % 12]
        
        # Adicionar variação sazonal simples
        seasonal_factor = 1.0
        if month_name in ['Dezembro', 'Janeiro']:  # Meses de alta
            seasonal_factor = 1.3
        elif month_name in ['Fevereiro', 'Março']:  # Meses de baixa
            seasonal_factor = 0.8
        
        # Adicionar crescimento ao longo do tempo
        growth_factor = 1 + (i * 0.02)  # 2% de crescimento por mês
        
        # Adicionar ruído aleatório
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

# Função de teste/exemplo
if __name__ == "__main__":
    print("=== TESTE DO SIMULADOR DE CENÁRIOS ===")
    
    # Criar dados de exemplo
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
        
        # Mostrar detalhes dos meses afetados pela sazonalidade
        affected_months = ['Dezembro', 'Janeiro', 'Fevereiro']
        print(f"\nDETALHES DOS MESES COM SAZONALIDADE:")
        for month in affected_months:
            month_data = df_pessimistic[df_pessimistic['mes'] == month]
            if not month_data.empty:
                print(f"{month}: Receita R$ {month_data['receita_total'].iloc[0]:,.2f}, "
                      f"Fluxo R$ {month_data['fluxo_de_caixa'].iloc[0]:,.2f}")
        
        # Gerar resumo comparativo
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