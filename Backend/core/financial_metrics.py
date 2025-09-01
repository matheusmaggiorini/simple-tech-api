import pandas as pd

def calcular_prazos_medios(df: pd.DataFrame, periodo_dias: int = 30):
    """
    Calcula os Prazos Médios (PMR, PMP, PME) a partir de um DataFrame contábil.
    Esta versão usa fórmulas contábeis mais diretas e robustas.
    """
    
    # Validação para garantir que o arquivo enviado tem as colunas corretas
    colunas_necessarias = [
        'receita_vendas_a_prazo', 'contas_a_receber', 'compras_fornecedores',
        'contas_a_pagar', 'custo_mercadoria_vendida', 'estoque_medio'
    ]
    for col in colunas_necessarias:
        if col not in df.columns:
            raise ValueError(f"Coluna contábil necessária '{col}' não encontrada no arquivo.")

    # Converte os dados para numérico, tratando erros e valores nulos
    df[colunas_necessarias] = df[colunas_necessarias].apply(pd.to_numeric, errors='coerce').fillna(0)

    # Define o número total de dias no período analisado (ex: 12 meses * 30 dias = 360)
    dias_no_periodo = len(df) * periodo_dias

    # --- Cálculo do PMR (Prazo Médio de Recebimento) ---
    # Fórmula Padrão: (Saldo Médio de Contas a Receber / Receita Total a Prazo) * Dias no Período
    media_contas_a_receber = df['contas_a_receber'].mean()
    total_vendas_a_prazo = df['receita_vendas_a_prazo'].sum()
    
    pmr = (media_contas_a_receber / total_vendas_a_prazo) * dias_no_periodo if total_vendas_a_prazo > 0 else 0

    # --- Cálculo do PMP (Prazo Médio de Pagamento) ---
    # Fórmula Padrão: (Saldo Médio de Contas a Pagar / Compras Totais) * Dias no Período
    media_contas_a_pagar = df['contas_a_pagar'].mean()
    total_compras = df['compras_fornecedores'].sum()

    pmp = (media_contas_a_pagar / total_compras) * dias_no_periodo if total_compras > 0 else 0

    # --- Cálculo do PME (Prazo Médio de Estoque) ---
    # Fórmula Padrão: (Estoque Médio / Custo Total da Mercadoria Vendida) * Dias no Período
    media_estoque = df['estoque_medio'].mean()
    total_cmv = df['custo_mercadoria_vendida'].sum()
    
    pme = (media_estoque / total_cmv) * dias_no_periodo if total_cmv > 0 else 0

    return {
        "pmr_dias": round(pmr, 2),
        "pmp_dias": round(pmp, 2),
        "pme_dias": round(pme, 2)
    }