import pandas as pd


def suggest_loan_options(df: pd.DataFrame):
    """
    Analisa o histórico de fluxo de caixa para sugerir dois cenários de empréstimo.
    """
    if df is None or df.empty:
        return {}

    df = df.copy()
    # Garantir colunas mínimas
    if 'data' not in df.columns:
        return {}
    if 'entrada' not in df.columns:
        df['entrada'] = 0.0
    if 'saida' not in df.columns:
        df['saida'] = 0.0
    if 'fluxo_diario' not in df.columns:
        df['fluxo_diario'] = pd.to_numeric(df['entrada'], errors='coerce').fillna(0) - pd.to_numeric(df['saida'], errors='coerce').fillna(0)

    # Sugestão 1: "SOS do Caixa" (Capital de Giro de Emergência)
    df['mes'] = pd.to_datetime(df['data']).dt.to_period('M')
    monthly_flow = df.groupby('mes')['fluxo_diario'].sum()
    worst_month_deficit = abs(monthly_flow[monthly_flow < 0].min()) if not monthly_flow[monthly_flow < 0].empty else 0
    sos_amount = worst_month_deficit * 1.20  # Cobre o pior mês + 20% de margem

    # Sugestão 2: "Fôlego para Operar" (Capital de Giro Estratégico)
    avg_monthly_costs = df.groupby('mes')['saida'].sum().mean()
    breathing_room_amount = avg_monthly_costs * 3  # Cobre 3 meses de custos

    # Lógica simples para estimar parcela (ex: juros de 2.5% a.m.)
    # A fórmula real da Tabela Price é mais complexa, mas isso serve para uma estimativa
    sos_installment = (sos_amount * 0.025) / (1 - (1 + 0.025)**-12) if sos_amount > 0 else 0
    breathing_room_installment = (breathing_room_amount * 0.025) / (1 - (1 + 0.025)**-24) if breathing_room_amount > 0 else 0

    return {
        "sos_loan": {
            "title": "SOS do Caixa",
            "description": "Para cobrir suas despesas mais urgentes e garantir o capital de giro imediato.",
            "suggested_amount": round(sos_amount, 2),
            "common_term_months": 12,
            "estimated_installment": round(sos_installment, 2)
        },
        "strategic_loan": {
            "title": "Fôlego para Operar",
            "description": "Para garantir 3 meses de operação, permitindo que você foque em crescer.",
            "suggested_amount": round(breathing_room_amount, 2),
            "common_term_months": 24,
            "estimated_installment": round(breathing_room_installment, 2)
        }
    }


