import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
import os
import sys

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.data_processing import processar_dados
# Importa o 'state' para podermos salvar os resultados
from api.endpoints import state

class CashflowPredictor:
    def __init__(self):
        self.model = XGBRegressor(random_state=42)
        self.best_model_ = None
        self.feature_columns = []
        self.dias_de_evento = {
            'dia_pagamento': [5, 20],
            'fim_de_mes': [28, 29, 30, 31]
        }

    def _extrair_features_avancado(self, df: pd.DataFrame) -> pd.DataFrame:
        df_diario = df.set_index('data').resample('D').agg({
            'fluxo_diario': 'sum'
        }).fillna(0)
        
        df_pivot = df.pivot_table(index='data', columns='categoria', values='fluxo_diario', aggfunc='sum').fillna(0)
        df_diario = df_diario.join(df_pivot, how='left').fillna(0)
        
        df_diario['dia_da_semana'] = df_diario.index.dayofweek
        df_diario['dia_do_mes'] = df_diario.index.day
        df_diario['mes'] = df_diario.index.month
        df_diario['semana_do_ano'] = df_diario.index.isocalendar().week.astype(int)
        
        df_diario['evento_pagamento'] = df_diario['dia_do_mes'].isin(self.dias_de_evento['dia_pagamento']).astype(int)
        df_diario['evento_fim_de_mes'] = df_diario['dia_do_mes'].isin(self.dias_de_evento['fim_de_mes']).astype(int)
        
        df_diario['lag_1_dia_fluxo'] = df_diario['fluxo_diario'].shift(1).fillna(0)
        df_diario['media_movel_7d_fluxo'] = df_diario['fluxo_diario'].rolling(window=7).mean().fillna(df_diario['fluxo_diario'])
        
        for cat in df['categoria'].unique():
            if cat not in df_diario.columns:
                df_diario[cat] = 0

        self.feature_columns = [col for col in df_diario.columns if col != 'fluxo_diario']
        
        return df_diario.reset_index()

    def train(self, df: pd.DataFrame):
        df_diario = self._extrair_features_avancado(df)
        
        # Garante que a coluna 'data' não seja usada como feature
        X = df_diario[self.feature_columns].drop(columns=['data'], errors='ignore')
        y = df_diario['fluxo_diario']

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.15, random_state=42, shuffle=False)

        print("\n--- INICIANDO TREINAMENTO FINAL (COM EXTRAÇÃO DE INSIGHTS) ---")
        
        best_params = {'learning_rate': 0.1, 'max_depth': 3, 'n_estimators': 300, 'subsample': 0.7}
        self.model.set_params(**best_params)

        print(f"Treinando modelo final com a configuração: {best_params}")
        self.model.fit(X_train, y_train)
        self.best_model_ = self.model

        # --- NOVA PARTE: EXTRAÇÃO DA IMPORTÂNCIA DAS FEATURES ---
        print("Extraindo e salvando a importância das features...")
        importances = self.best_model_.feature_importances_
        feature_names = X.columns
        
        # Cria um DataFrame para visualizar e ordenar os resultados
        feature_importance_df = pd.DataFrame({
            'feature': feature_names,
            'importance': importances
        }).sort_values(by='importance', ascending=False)
        
        # Salva o resultado no estado global para a API usar
        state.global_feature_importance = feature_importance_df.to_dict(orient='records')
        print("Insights salvos com sucesso.")
        # --- FIM DA NOVA PARTE ---

        preds = self.best_model_.predict(X_test)

        mae = mean_absolute_error(y_test, preds)
        mse = mean_squared_error(y_test, preds)
        r2 = r2_score(y_test, preds)

        print("\n--- AVALIAÇÃO DO MODELO FINAL ---")
        print(f"Resultado Final -> MAE: R$ {mae:.2f}, MSE: {mse:.2f}, R²: {r2:.2f}")
        print("---------------------------------\n")

    def predict(self, future_days: int, df_historico: pd.DataFrame):
        if self.best_model_ is None:
            raise ValueError("O modelo ainda não foi treinado.")
        print("AVISO: A função de previsão futura precisaria ser atualizada.")
        return pd.DataFrame()


if __name__ == '__main__':
    # ... (o bloco de execução para teste continua o mesmo)
    print("Executando o script 'cashflow_predictor.py' em modo de otimização final.")
    caminho_dados = os.path.join(os.path.dirname(__file__), '..', 'data', 'api_uploads', 'dados_financeiros_treinamento.csv')
    try:
        df_dados = pd.read_csv(caminho_dados)
        df_processado = processar_dados(df_dados)
        print("Dados carregados e processados com sucesso.")
        predictor = CashflowPredictor()
        predictor.train(df_processado)
    except FileNotFoundError:
        print(f"ERRO: Arquivo de dados não encontrado em '{caminho_dados}'.")
    except Exception as e:
        print(f"Ocorreu um erro inesperado: {e}")