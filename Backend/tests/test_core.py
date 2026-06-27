# tests/test_core.py

import os
import sys
from datetime import datetime, timedelta

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core import customer_analysis, data_processing, risk_analyzer, scenario_simulator
from core.cashflow_predictor import CashflowPredictor


@pytest.fixture
def sample_raw_data_dict():
    return {
        "data": [
            "2023-01-01",
            "2023-01-02",
            "2023-01-03",
            "2023-01-04",
            "2023-01-05",
        ],
        "descricao": ["Venda A", "Pagamento X", "Venda B", "Despesa Y", "Venda C"],
        "entrada": [100.0, 0.0, 150.0, 0.0, 200.0],
        "saida": [0.0, 50.0, 0.0, 75.0, 0.0],
    }


@pytest.fixture
def sample_raw_dataframe(sample_raw_data_dict):
    return pd.DataFrame(sample_raw_data_dict)


@pytest.fixture
def sample_processed_dataframe(sample_raw_dataframe):
    return data_processing.processar_dados(sample_raw_dataframe.copy(), filename="test.csv")


def test_processar_dados_colunas_essenciais(sample_raw_dataframe):
    df_processed = data_processing.processar_dados(sample_raw_dataframe.copy(), filename="test.csv")
    assert df_processed is not None
    assert "data" in df_processed.columns
    assert "fluxo_diario" in df_processed.columns
    assert "saldo" in df_processed.columns
    assert pd.api.types.is_datetime64_any_dtype(df_processed["data"])


def test_processar_dados_calculo_fluxo_saldo(sample_raw_dataframe):
    df_copy = sample_raw_dataframe.copy()
    df_processed = data_processing.processar_dados(df_copy, filename="test.csv")
    expected_fluxo_dia1 = df_copy.loc[0, "entrada"] - df_copy.loc[0, "saida"]
    first_row = df_processed[df_processed["descricao"] == df_copy.loc[0, "descricao"]]
    assert not first_row.empty
    assert first_row["fluxo_diario"].iloc[0] == expected_fluxo_dia1


def test_identificar_riscos_com_base_em_limiares():
    df_previsoes = pd.DataFrame(
        {
            "data": pd.to_datetime(["2023-02-01", "2023-02-02", "2023-02-03"]),
            "saldo_previsto": [-100, -200, -50],
        }
    )
    analyzer = risk_analyzer.RiskAnalyzer()
    alertas = analyzer.identificar_riscos_com_base_em_limiares(df_previsoes, saldo_inicial=500)
    assert isinstance(alertas, list)
    assert len(alertas) > 0


def test_validate_forecast_dataframe():
    df = scenario_simulator.create_sample_forecast_data(months=3)
    assert scenario_simulator.validate_forecast_dataframe(df) is True


def test_run_macroeconomic_simulation():
    df = scenario_simulator.create_sample_forecast_data(months=6)
    result = scenario_simulator.run_simulation(df, scenario_type="mais_provavel")
    assert result is not None
    assert not result.empty


def test_cashflow_predictor_train_and_predict(sample_processed_dataframe):
    if sample_processed_dataframe is None or len(sample_processed_dataframe) < 3:
        pytest.skip("Not enough rows for predictor test.")
    predictor = CashflowPredictor()
    predictor.train(sample_processed_dataframe)
    if predictor.best_model_ is None:
        pytest.skip("Not enough data to train predictor.")
    forecast = predictor.predict(5, sample_processed_dataframe)
    assert forecast is not None
    assert len(forecast) == 5


@pytest.fixture
def sample_faturas_data():
    data_hoje = datetime.now()
    return {
        "id_cliente": ["C001", "C001", "C002"],
        "data_vencimento": [
            data_hoje - timedelta(days=10),
            data_hoje - timedelta(days=40),
            data_hoje - timedelta(days=5),
        ],
        "data_pagamento": [None, data_hoje - timedelta(days=30), None],
        "valor_fatura": [100.0, 250.0, 50.0],
    }


@pytest.fixture
def df_faturas_exemplo(sample_faturas_data):
    df = pd.DataFrame(sample_faturas_data)
    df["data_vencimento"] = pd.to_datetime(df["data_vencimento"])
    df["data_pagamento"] = pd.to_datetime(df["data_pagamento"], errors="coerce")
    return df


def test_calcular_dias_atraso(df_faturas_exemplo):
    df_analise = customer_analysis.calcular_dias_atraso(df_faturas_exemplo.copy())
    assert "status_pagamento" in df_analise.columns
    assert "dias_atraso" in df_analise.columns


def test_segmentar_clientes_por_risco_inadimplencia(df_faturas_exemplo):
    df_analise = customer_analysis.calcular_dias_atraso(df_faturas_exemplo.copy())
    df_segmentado = customer_analysis.segmentar_clientes_por_risco_inadimplencia(df_analise)
    assert df_segmentado is None or "risco_inadimplencia" in df_segmentado.columns


def test_gerar_relatorio_inadimplencia(df_faturas_exemplo):
    df_analise = customer_analysis.calcular_dias_atraso(df_faturas_exemplo.copy())
    df_segmentado = customer_analysis.segmentar_clientes_por_risco_inadimplencia(df_analise)
    relatorio = customer_analysis.gerar_relatorio_inadimplencia(df_segmentado)
    assert isinstance(relatorio, dict)
    assert "total_clientes_com_faturas_em_atraso" in relatorio
