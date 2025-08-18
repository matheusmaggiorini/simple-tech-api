# core/customer_analysis.py

import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any


# Este módulo foca na análise de inadimplência de clientes.
# Requer que o DataFrame de entrada contenha colunas como:
# - id_cliente (identificador único do cliente)
# - data_vencimento (data de vencimento da fatura)
# - data_pagamento (data em que a fatura foi paga, NaN ou NaT se não paga)
# - valor_fatura (valor da fatura)

def calcular_dias_atraso(df: pd.DataFrame, data_referencia: Optional[datetime] = None) -> pd.DataFrame:
    """Calcula os dias de atraso para faturas não pagas e o status de pagamento."""
    if df.empty:
        return df
    
    df_copia = df.copy()
    
    if data_referencia is None:
        data_referencia = datetime.now()
    
    # Garantir que as colunas de data são do tipo datetime
    colunas_data = ["data_vencimento", "data_pagamento"]
    for col in colunas_data:
        if col in df_copia.columns and not pd.api.types.is_datetime64_any_dtype(df_copia[col]):
            df_copia[col] = pd.to_datetime(df_copia[col], errors="coerce")

    if "data_vencimento" not in df_copia.columns or "valor_fatura" not in df_copia.columns:
        print("Erro: Colunas 'data_vencimento' e 'valor_fatura' são necessárias para análise de inadimplência.")
        # Retornar colunas vazias para evitar erros subsequentes se não existirem
        df_copia["status_pagamento"] = "Dados Insuficientes"
        df_copia["dias_atraso"] = 0
        return df_copia

    # Status de pagamento
    def determinar_status(row):
        if "data_pagamento" in row and pd.notna(row["data_pagamento"]):
            if row["data_pagamento"] <= row["data_vencimento"]:
                return "Pago em Dia"
            else:
                return "Pago com Atraso"
        elif pd.notna(row["data_vencimento"]):
            if row["data_vencimento"] < data_referencia:
                return "Em Atraso"
            else:
                return "A Vencer"
        else:
            return "Indefinido"

    df_copia["status_pagamento"] = df_copia.apply(determinar_status, axis=1)

    # Calcular dias de atraso
    def calcular_dias(row):
        if row["status_pagamento"] == "Pago com Atraso":
            return (row["data_pagamento"] - row["data_vencimento"]).days
        elif row["status_pagamento"] == "Em Atraso":
            return (data_referencia - row["data_vencimento"]).days
        return 0

    df_copia["dias_atraso"] = df_copia.apply(calcular_dias, axis=1)
    df_copia["dias_atraso"] = df_copia["dias_atraso"].astype(int)
    
    print("Cálculo de dias de atraso e status de pagamento concluído.")
    return df_copia

def segmentar_clientes_por_risco_inadimplencia(df_com_atraso: pd.DataFrame) -> Optional[pd.DataFrame]:
    """Segmenta clientes com base no histórico de atraso e valores devidos."""
    if df_com_atraso.empty or "id_cliente" not in df_com_atraso.columns:
        print("DataFrame vazio ou sem 'id_cliente' para segmentação.")
        return None

    # Focar apenas em faturas "Em Atraso"
    df_em_atraso = df_com_atraso[df_com_atraso["status_pagamento"] == "Em Atraso"].copy()
    if df_em_atraso.empty:
        print("Nenhuma fatura atualmente em atraso para segmentação.")
        # Poderíamos retornar um df vazio com as colunas esperadas ou None
        # Para consistência, vamos retornar um df com as colunas, mas vazio.
        return pd.DataFrame(columns=["id_cliente", "total_devido_atraso", "max_dias_atraso", "num_faturas_atraso", "risco_inadimplencia"])

    # Agrupar por cliente
    sumario_cliente = df_em_atraso.groupby("id_cliente").agg(
        total_devido_atraso=("valor_fatura", "sum"),
        max_dias_atraso=("dias_atraso", "max"),
        num_faturas_atraso=("id_cliente", "count") # Qualquer coluna não nula serviria para contar
    ).reset_index()

    # Definir regras de segmentação de risco (exemplo simples)
    # Baixo Risco: até 30 dias de atraso E valor total < 500
    # Médio Risco: (31-60 dias de atraso OU valor total 500-2000) E não Alto Risco
    # Alto Risco: > 60 dias de atraso OU valor total > 2000
    def classificar_risco(row):
        if row["max_dias_atraso"] > 60 or row["total_devido_atraso"] > 2000:
            return "Alto"
        elif (row["max_dias_atraso"] > 30 and row["max_dias_atraso"] <= 60) or \
             (row["total_devido_atraso"] >= 500 and row["total_devido_atraso"] <= 2000):
            return "Médio"
        else:
            return "Baixo"

    sumario_cliente["risco_inadimplencia"] = sumario_cliente.apply(classificar_risco, axis=1)
    
    print("Segmentação de clientes por risco de inadimplência concluída.")
    return sumario_cliente.sort_values(by="total_devido_atraso", ascending=False)

def gerar_relatorio_inadimplencia(df_segmentado: Optional[pd.DataFrame]) -> Dict[str, Any]:
    """Gera um relatório resumido da análise de inadimplência."""
    relatorio = {
        "total_clientes_com_faturas_em_atraso": 0,
        "valor_total_em_atraso": 0.0,
        "distribuicao_risco": {"Alto": 0, "Médio": 0, "Baixo": 0},
        "top_5_clientes_alto_risco": []
    }

    if df_segmentado is None or df_segmentado.empty:
        print("Nenhum dado segmentado para gerar relatório de inadimplência.")
        return relatorio

    relatorio["total_clientes_com_faturas_em_atraso"] = len(df_segmentado)
    relatorio["valor_total_em_atraso"] = df_segmentado["total_devido_atraso"].sum()
    
    contagem_risco = df_segmentado["risco_inadimplencia"].value_counts().to_dict()
    for risco, contagem in contagem_risco.items():
        if risco in relatorio["distribuicao_risco"]:
            relatorio["distribuicao_risco"][risco] = contagem
            
    top_5_alto_risco = df_segmentado[df_segmentado["risco_inadimplencia"] == "Alto"].head(5)
    relatorio["top_5_clientes_alto_risco"] = top_5_alto_risco.to_dict(orient="records")
    
    print("Relatório de inadimplência gerado.")
    return relatorio


if __name__ == "__main__":
    # Exemplo de uso
    # Criar um DataFrame de exemplo com dados de faturas
    data_hoje = datetime.now()
    dados_faturas = {
        "id_cliente": ["C001", "C001", "C002", "C003", "C002", "C004", "C001", "C005", "C003"],
        "data_vencimento": [
            data_hoje - timedelta(days=10), # C001 - Em Atraso
            data_hoje - timedelta(days=40), # C001 - Em Atraso
            data_hoje - timedelta(days=5),  # C002 - Em Atraso
            data_hoje + timedelta(days=15), # C003 - A Vencer
            data_hoje - timedelta(days=70), # C002 - Em Atraso (Alto Risco)
            data_hoje - timedelta(days=20), # C004 - Em Atraso
            data_hoje - timedelta(days=50), # C001 - Pago com Atraso
            data_hoje - timedelta(days=35), # C005 - Em Atraso
            data_hoje - timedelta(days=5),  # C003 - Pago em Dia
        ],
        "data_pagamento": [
            None, 
            None, 
            None, 
            None, 
            None, 
            None, 
            data_hoje - timedelta(days=30), # C001 - Pago com 20 dias de atraso
            None,
            data_hoje - timedelta(days=6),  # C003 - Pago 1 dia antes
        ],
        "valor_fatura": [100.0, 250.0, 50.0, 300.0, 1200.0, 80.0, 500.0, 2200.0, 75.0]
    }
    df_faturas_exemplo = pd.DataFrame(dados_faturas)
    df_faturas_exemplo["data_vencimento"] = pd.to_datetime(df_faturas_exemplo["data_vencimento"])
    df_faturas_exemplo["data_pagamento"] = pd.to_datetime(df_faturas_exemplo["data_pagamento"], errors="coerce")

    print("--- DataFrame de Faturas de Exemplo ---")
    print(df_faturas_exemplo)
    print("\n--- Tipos de Dados Iniciais ---")
    print(df_faturas_exemplo.dtypes)

    # Calcular dias de atraso e status
    df_analise_inadimplencia = calcular_dias_atraso(df_faturas_exemplo, data_referencia=data_hoje)
    print("\n--- DataFrame com Análise de Atraso ---")
    print(df_analise_inadimplencia[["id_cliente", "data_vencimento", "data_pagamento", "valor_fatura", "status_pagamento", "dias_atraso"]])

    # Segmentar clientes por risco
    df_segmentado = segmentar_clientes_por_risco_inadimplencia(df_analise_inadimplencia)
    if df_segmentado is not None:
        print("\n--- Clientes Segmentados por Risco de Inadimplência (Faturas em Atraso) ---")
        print(df_segmentado)
    else:
        print("\nNenhuma segmentação de risco gerada.")

    # Gerar relatório de inadimplência
    relatorio = gerar_relatorio_inadimplencia(df_segmentado)
    print("\n--- Relatório de Inadimplência ---")
    print(f'Total de clientes com faturas em atraso: {relatorio["total_clientes_com_faturas_em_atraso"]}')
    print(f"Valor total em atraso: R$ {relatorio['valor_total_em_atraso']:.2f}")
    print(f"Distribuição de Risco: Alto={relatorio['distribuicao_risco']['Alto']}, Médio={relatorio['distribuicao_risco']['Médio']}, Baixo={relatorio['distribuicao_risco']['Baixo']}")
    print("Top 5 Clientes de Alto Risco (em atraso):")
    if relatorio["top_5_clientes_alto_risco"]:
        for cliente in relatorio["top_5_clientes_alto_risco"]:
            print(f"  - ID: {cliente['id_cliente']}, Devido: R$ {cliente['total_devido_atraso']:.2f}, Max Dias Atraso: {cliente['max_dias_atraso']}")
    else:
        print("  Nenhum cliente classificado como alto risco atualmente em atraso.")

