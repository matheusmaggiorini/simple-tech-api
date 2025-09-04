# core/scenario_simulator.py

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import logging

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
    required_columns = ['mes', 'receita_total', 'custo_total', 'fluxo_de_caixa']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        raise ValueError(f"DataFrame deve conter as colunas: {', '.join(missing_columns)}")
    
    if df.empty:
        raise ValueError("DataFrame não pode estar vazio")
    
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
    
    logger.info(f"Aplicando cenário {scenario_type}: receita {revenue_multiplier:.2%}, custo {cost_multiplier:.2%}")
    
    # Ajustar receita e custo
    df_adjusted['receita_total'] = df_adjusted['receita_total'] * revenue_multiplier
    df_adjusted['custo_total'] = df_adjusted['custo_total'] * cost_multiplier
    
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
    df_seasonal = df.copy()
    
    logger.info(f"Aplicando {len(seasonality_rules)} regras de sazonalidade")
    
    for rule in seasonality_rules:
        month = rule.get("month")
        revenue_change = rule.get("revenue_change_percentage", 0)
        
        if not month or revenue_change is None:
            logger.warning(f"Regra de sazonalidade inválida: {rule}")
            continue
        
        # Encontrar linhas correspondentes ao mês
        month_mask = df_seasonal['mes'].str.contains(month, case=False, na=False)
        matching_rows = df_seasonal[month_mask]
        
        if matching_rows.empty:
            logger.warning(f"Nenhum registro encontrado para o mês: {month}")
            continue
        
        # Aplicar mudança percentual apenas na receita
        multiplier = 1 + (revenue_change / 100)
        df_seasonal.loc[month_mask, 'receita_total'] *= multiplier
        
        logger.info(f"Ajuste sazonal aplicado ao mês {month}: {revenue_change:+.1f}% na receita")
        logger.info(f"Registros afetados: {len(matching_rows)}")
    
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
    df_recalculated['fluxo_de_caixa'] = df_recalculated['receita_total'] - df_recalculated['custo_total']
    
    logger.info("Fluxo de caixa recalculado após ajustes")
    
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
        
    Example:
        >>> df = pd.DataFrame({
        ...     'mes': ['Janeiro', 'Fevereiro', 'Março'],
        ...     'receita_total': [1000, 1100, 1200],
        ...     'custo_total': [800, 850, 900],
        ...     'fluxo_de_caixa': [200, 250, 300]
        ... })
        >>> seasonality = [{"month": "Fevereiro", "revenue_change_percentage": -15}]
        >>> result = run_simulation(df, 'otimista', seasonality)
    """
    logger.info("Iniciando simulação de cenários")
    logger.info(f"Cenário: {scenario_type}")
    logger.info(f"Regras de sazonalidade: {len(seasonality_rules) if seasonality_rules else 0}")
    
    # 1. Validar DataFrame de entrada
    validate_forecast_dataframe(forecast_df)
    
    # 2. Criar cópia do DataFrame original
    df_simulation = forecast_df.copy()
    logger.info(f"DataFrame original: {len(df_simulation)} registros")
    
    # 3. Aplicar ajustes de cenário macroeconômico
    df_simulation = apply_macroeconomic_scenario(df_simulation, scenario_type)
    
    # 4. Aplicar ajustes de sazonalidade (se fornecidos)
    if seasonality_rules and len(seasonality_rules) > 0:
        df_simulation = apply_seasonality_adjustments(df_simulation, seasonality_rules)
    
    # 5. Recalcular fluxo de caixa
    df_simulation = recalculate_cash_flow(df_simulation)
    
    logger.info("Simulação de cenários concluída com sucesso")
    
    return df_simulation

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
    original_totals = {
        "receita": original_df['receita_total'].sum(),
        "custo": original_df['custo_total'].sum(),
        "fluxo": original_df['fluxo_de_caixa'].sum()
    }
    
    simulated_totals = {
        "receita": simulated_df['receita_total'].sum(),
        "custo": simulated_df['custo_total'].sum(),
        "fluxo": simulated_df['fluxo_de_caixa'].sum()
    }
    
    changes = {
        "receita_change": ((simulated_totals["receita"] - original_totals["receita"]) / original_totals["receita"]) * 100,
        "custo_change": ((simulated_totals["custo"] - original_totals["custo"]) / original_totals["custo"]) * 100,
        "fluxo_change": ((simulated_totals["fluxo"] - original_totals["fluxo"]) / original_totals["fluxo"]) * 100 if original_totals["fluxo"] != 0 else 0
    }
    
    summary = {
        "scenario_type": scenario_type,
        "scenario_description": MACROECONOMIC_SCENARIOS[scenario_type]["description"],
        "original_totals": original_totals,
        "simulated_totals": simulated_totals,
        "percentage_changes": changes,
        "months_analyzed": len(original_df),
        "positive_cash_flow_months_original": int((original_df['fluxo_de_caixa'] > 0).sum()),
        "positive_cash_flow_months_simulated": int((simulated_df['fluxo_de_caixa'] > 0).sum())
    }
    
    return summary

# Simulação de Monte Carlo para fluxo de caixa (funcionalidade existente mantida)
def calcular_estatisticas_historicas(df_historico: pd.DataFrame) -> Dict[str, Any]:
    """Calcula estatísticas básicas do histórico de fluxo de caixa para uso na simulação."""
    if df_historico.empty or "data" not in df_historico.columns:
        raise ValueError("DataFrame histórico vazio ou sem coluna 'data'.")
    
    estatisticas = {}
    
    # Verificar se temos colunas de entrada e saída ou fluxo diário
    if "entrada" in df_historico.columns and "saida" in df_historico.columns:
        # Calcular estatísticas de entrada
        estatisticas["media_entrada"] = df_historico["entrada"].mean()
        estatisticas["desvio_padrao_entrada"] = df_historico["entrada"].std()
        estatisticas["min_entrada"] = df_historico["entrada"].min()
        estatisticas["max_entrada"] = df_historico["entrada"].max()
        
        # Calcular estatísticas de saída
        estatisticas["media_saida"] = df_historico["saida"].mean()
        estatisticas["desvio_padrao_saida"] = df_historico["saida"].std()
        estatisticas["min_saida"] = df_historico["saida"].min()
        estatisticas["max_saida"] = df_historico["saida"].max()
    
    # Calcular estatísticas de fluxo diário (entrada - saída)
    if "fluxo_diario" in df_historico.columns:
        estatisticas["media_fluxo"] = df_historico["fluxo_diario"].mean()
        estatisticas["desvio_padrao_fluxo"] = df_historico["fluxo_diario"].std()
    elif "entrada" in df_historico.columns and "saida" in df_historico.columns:
        df_historico["fluxo_diario"] = df_historico["entrada"] - df_historico["saida"]
        estatisticas["media_fluxo"] = df_historico["fluxo_diario"].mean()
        estatisticas["desvio_padrao_fluxo"] = df_historico["fluxo_diario"].std()
    
    # Calcular estatísticas de saldo, se disponível
    if "saldo" in df_historico.columns:
        estatisticas["ultimo_saldo"] = df_historico["saldo"].iloc[-1]
        estatisticas["media_saldo"] = df_historico["saldo"].mean()
        estatisticas["desvio_padrao_saldo"] = df_historico["saldo"].std()
    
    # Calcular estatísticas temporais
    df_historico_sorted = df_historico.sort_values(by="data")
    estatisticas["primeira_data"] = df_historico_sorted["data"].iloc[0]
    estatisticas["ultima_data"] = df_historico_sorted["data"].iloc[-1]
    estatisticas["dias_historico"] = (estatisticas["ultima_data"] - estatisticas["primeira_data"]).days + 1
    
    return estatisticas

def gerar_parametros_simulacao(
    estatisticas: Dict[str, Any],
    variacao_entrada: float = 0.1,  # Variação percentual na média de entradas
    variacao_saida: float = 0.1,    # Variação percentual na média de saídas
    dias_simulacao: int = 30,       # Número de dias a simular
    num_simulacoes: int = 1000,     # Número de simulações de Monte Carlo
    saldo_inicial: Optional[float] = None,  # Saldo inicial para a simulação
    seed: Optional[int] = None      # Seed para reprodutibilidade
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
        # Aplicar variação à média de entradas
        parametros["media_entrada_base"] = estatisticas["media_entrada"]
        parametros["media_entrada_min"] = estatisticas["media_entrada"] * (1 - variacao_entrada)
        parametros["media_entrada_max"] = estatisticas["media_entrada"] * (1 + variacao_entrada)
        
        # Usar desvio padrão histórico ou um valor mínimo
        parametros["desvio_padrao_entrada"] = max(
            estatisticas.get("desvio_padrao_entrada", 0),
            estatisticas["media_entrada"] * 0.05  # Mínimo de 5% da média como desvio padrão
        )
    
    # Definir parâmetros de distribuição para saídas
    if "media_saida" in estatisticas:
        # Aplicar variação à média de saídas
        parametros["media_saida_base"] = estatisticas["media_saida"]
        parametros["media_saida_min"] = estatisticas["media_saida"] * (1 - variacao_saida)
        parametros["media_saida_max"] = estatisticas["media_saida"] * (1 + variacao_saida)
        
        # Usar desvio padrão histórico ou um valor mínimo
        parametros["desvio_padrao_saida"] = max(
            estatisticas.get("desvio_padrao_saida", 0),
            estatisticas["media_saida"] * 0.05  # Mínimo de 5% da média como desvio padrão
        )
    
    # Alternativa: usar estatísticas de fluxo diário se não temos entrada/saída separadas
    if "media_fluxo" in estatisticas and ("media_entrada_base" not in parametros):
        parametros["media_fluxo_base"] = estatisticas["media_fluxo"]
        parametros["media_fluxo_min"] = estatisticas["media_fluxo"] * (1 - variacao_entrada)  # Usando variação_entrada como proxy
        parametros["media_fluxo_max"] = estatisticas["media_fluxo"] * (1 + variacao_entrada)
        
        parametros["desvio_padrao_fluxo"] = max(
            estatisticas.get("desvio_padrao_fluxo", 0),
            abs(estatisticas["media_fluxo"]) * 0.05  # Mínimo de 5% da média como desvio padrão
        )
    
    return parametros

def executar_simulacao_monte_carlo(parametros: Dict[str, Any]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Executa a simulação de Monte Carlo para fluxo de caixa com base nos parâmetros fornecidos."""
    dias_simulacao = parametros["dias_simulacao"]
    num_simulacoes = parametros["num_simulacoes"]
    saldo_inicial = parametros["saldo_inicial"]
    data_inicio = parametros["data_inicio_simulacao"]
    
    # Criar datas para a simulação
    datas_simulacao = [data_inicio + timedelta(days=i) for i in range(dias_simulacao)]
    
    # Matriz para armazenar resultados de todas as simulações
    # Formato: [num_simulacoes, dias_simulacao]
    matriz_saldos = np.zeros((num_simulacoes, dias_simulacao))
    
    # Executar simulações
    for sim in range(num_simulacoes):
        saldo_atual = saldo_inicial
        
        for dia in range(dias_simulacao):
            # Gerar fluxo de caixa para o dia atual
            if "media_entrada_base" in parametros and "media_saida_base" in parametros:
                # Simular entrada e saída separadamente
                # Variação aleatória nas médias para esta simulação específica
                media_entrada_sim = np.random.uniform(
                    parametros["media_entrada_min"],
                    parametros["media_entrada_max"]
                )
                media_saida_sim = np.random.uniform(
                    parametros["media_saida_min"],
                    parametros["media_saida_max"]
                )
                
                # Gerar valores diários com distribuição normal
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
                # Variação aleatória na média para esta simulação específica
                media_fluxo_sim = np.random.uniform(
                    parametros["media_fluxo_min"],
                    parametros["media_fluxo_max"]
                )
                
                # Gerar valor de fluxo diário com distribuição normal
                fluxo_dia = np.random.normal(
                    media_fluxo_sim,
                    parametros["desvio_padrao_fluxo"]
                )
            
            else:
                raise ValueError("Parâmetros insuficientes para simulação. Necessário média de entrada/saída ou fluxo.")
            
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
    
    # Calcular probabilidades de eventos específicos
    # Exemplo: probabilidade de saldo negativo em cada dia
    prob_saldo_negativo = np.mean(matriz_saldos < 0, axis=0)
    df_resultados['prob_saldo_negativo'] = prob_saldo_negativo
    
    # Criar DataFrame com todas as simulações individuais (para visualização detalhada)
    df_simulacoes = pd.DataFrame(
        matriz_saldos.T,  # Transpor para ter dias nas linhas e simulações nas colunas
        index=datas_simulacao,
        columns=[f'sim_{i+1}' for i in range(num_simulacoes)]
    )
    
    return df_resultados, df_simulacoes

def visualizar_resultados_simulacao(df_resultados: pd.DataFrame, titulo: str = "Simulação de Monte Carlo - Fluxo de Caixa") -> plt.Figure:
    """Cria uma visualização dos resultados da simulação de Monte Carlo."""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Plotar área entre percentis 5 e 95 (90% de confiança)
    ax.fill_between(
        df_resultados.index,
        df_resultados['percentil_5'],
        df_resultados['percentil_95'],
        alpha=0.3,
        color='lightblue',
        label='Intervalo de 90% de confiança'
    )
    
    # Plotar área entre percentis 25 e 75 (50% de confiança)
    ax.fill_between(
        df_resultados.index,
        df_resultados['percentil_25'],
        df_resultados['percentil_75'],
        alpha=0.5,
        color='blue',
        label='Intervalo de 50% de confiança'
    )
    
    # Plotar mediana (percentil 50)
    ax.plot(
        df_resultados.index,
        df_resultados['percentil_50'],
        'b-',
        linewidth=2,
        label='Mediana'
    )
    
    # Plotar média
    ax.plot(
        df_resultados.index,
        df_resultados['media'],
        'r--',
        linewidth=1.5,
        label='Média'
    )
    
    # Adicionar linha horizontal em y=0
    ax.axhline(y=0, color='red', linestyle='-', alpha=0.3)
    
    # Configurar gráfico
    ax.set_title(titulo)
    ax.set_xlabel('Data')
    ax.set_ylabel('Saldo Projetado')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Formatar eixo x para datas
    fig.autofmt_xdate()
    
    return fig

def analisar_probabilidades(df_resultados: pd.DataFrame) -> Dict[str, Any]:
    """Analisa as probabilidades de eventos específicos com base nos resultados da simulação."""
    analise = {}
    
    # Probabilidade de saldo negativo no final do período
    analise["prob_saldo_negativo_final"] = df_resultados["prob_saldo_negativo"].iloc[-1]
    
    # Probabilidade de saldo negativo em qualquer momento
    analise["prob_saldo_negativo_qualquer_momento"] = df_resultados["prob_saldo_negativo"].max()
    
    # Dia com maior probabilidade de saldo negativo
    idx_max_prob_negativo = df_resultados["prob_saldo_negativo"].idxmax()
    analise["dia_maior_prob_negativo"] = idx_max_prob_negativo
    analise["valor_maior_prob_negativo"] = df_resultados["prob_saldo_negativo"].max()
    
    # Valor mínimo esperado (percentil 5 do último dia)
    analise["valor_minimo_esperado"] = df_resultados["percentil_5"].iloc[-1]
    
    # Valor máximo esperado (percentil 95 do último dia)
    analise["valor_maximo_esperado"] = df_resultados["percentil_95"].iloc[-1]
    
    # Valor mediano esperado (percentil 50 do último dia)
    analise["valor_mediano_esperado"] = df_resultados["percentil_50"].iloc[-1]
    
    return analise

if __name__ == "__main__":
    # Exemplo de uso da nova funcionalidade de simulação de cenários
    print("=== Exemplo de Simulação de Cenários ===")
    
    # Criar dados de exemplo para demonstração
    df_exemplo = pd.DataFrame({
        'mes': ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho'],
        'receita_total': [10000, 11000, 12000, 13000, 14000, 15000],
        'custo_total': [8000, 8500, 9000, 9500, 10000, 10500],
        'fluxo_de_caixa': [2000, 2500, 3000, 3500, 4000, 4500]
    })
    
    print("DataFrame Original:")
    print(df_exemplo)
    print(f"Total Receita Original: R$ {df_exemplo['receita_total'].sum():,.2f}")
    print(f"Total Custo Original: R$ {df_exemplo['custo_total'].sum():,.2f}")
    print(f"Total Fluxo Original: R$ {df_exemplo['fluxo_de_caixa'].sum():,.2f}")
    
    # Exemplo 1: Cenário otimista sem sazonalidade
    print("\n--- Cenário Otimista ---")
    df_otimista = run_simulation(df_exemplo, 'otimista')
    print(f"Total Receita Otimista: R$ {df_otimista['receita_total'].sum():,.2f}")
    print(f"Total Custo Otimista: R$ {df_otimista['custo_total'].sum():,.2f}")
    print(f"Total Fluxo Otimista: R$ {df_otimista['fluxo_de_caixa'].sum():,.2f}")
    
    # Exemplo 2: Cenário pessimista com sazonalidade
    print("\n--- Cenário Pessimista com Sazonalidade ---")
    regras_sazonalidade = [
        {"month": "Dezembro", "revenue_change_percentage": 30},
        {"month": "Fevereiro", "revenue_change_percentage": -15}
    ]
    
    # Para demonstração, vamos adicionar dezembro ao dataset
    df_exemplo_extended = pd.concat([
        df_exemplo,
        pd.DataFrame({
            'mes': ['Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'],
            'receita_total': [16000, 17000, 18000, 19000, 20000, 21000],
            'custo_total': [11000, 11500, 12000, 12500, 13000, 13500],
            'fluxo_de_caixa': [5000, 5500, 6000, 6500, 7000, 7500]
        })
    ], ignore_index=True)
    
    df_pessimista_sazonal = run_simulation(
        df_exemplo_extended, 
        'pessimista', 
        regras_sazonalidade
    )
    
    print(f"Total Receita Pessimista c/ Sazonalidade: R$ {df_pessimista_sazonal['receita_total'].sum():,.2f}")
    print(f"Total Custo Pessimista c/ Sazonalidade: R$ {df_pessimista_sazonal['custo_total'].sum():,.2f}")
    print(f"Total Fluxo Pessimista c/ Sazonalidade: R$ {df_pessimista_sazonal['fluxo_de_caixa'].sum():,.2f}")
    
    # Mostrar detalhes de dezembro e fevereiro
    dezembro = df_pessimista_sazonal[df_pessimista_sazonal['mes'] == 'Dezembro']
    fevereiro = df_pessimista_sazonal[df_pessimista_sazonal['mes'] == 'Fevereiro']
    
    if not dezembro.empty:
        print(f"\nDezembro - Receita: R$ {dezembro['receita_total'].iloc[0]:,.2f}")
        print(f"Dezembro - Fluxo: R$ {dezembro['fluxo_de_caixa'].iloc[0]:,.2f}")
    
    if not fevereiro.empty:
        print(f"Fevereiro - Receita: R$ {fevereiro['receita_total'].iloc[0]:,.2f}")
        print(f"Fevereiro - Fluxo: R$ {fevereiro['fluxo_de_caixa'].iloc[0]:,.2f}")
    
    # Gerar resumo comparativo
    print("\n--- Resumo Comparativo ---")
    resumo = generate_scenario_summary(df_exemplo_extended, df_pessimista_sazonal, 'pessimista')
    print(f"Mudança na Receita: {resumo['percentage_changes']['receita_change']:+.1f}%")
    print(f"Mudança no Custo: {resumo['percentage_changes']['custo_change']:+.1f}%")
    print(f"Mudança no Fluxo: {resumo['percentage_changes']['fluxo_change']:+.1f}%")