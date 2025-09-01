import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
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
        self.original_categories = []

    def _extrair_features_avancado(self, df: pd.DataFrame) -> pd.DataFrame:
        if 'categoria' not in df.columns:
            df['categoria'] = 'outros'
        df['categoria'] = df['categoria'].fillna('outros')
        
        self.original_categories = df['categoria'].unique().tolist()
        
        df_diario_base = df.set_index('data').resample('D').agg({'fluxo_diario': 'sum'}).fillna(0)
        df_pivot = df.pivot_table(index='data', columns='categoria', values='fluxo_diario', aggfunc='sum').fillna(0)
        
        df_pivot.index = pd.to_datetime(df_pivot.index)
        df_pivot = df_pivot.resample('D').sum().fillna(0)

        df_diario = df_diario_base.join(df_pivot, how='left').fillna(0)
        
        df_diario['dia_da_semana'] = df_diario.index.dayofweek
        df_diario['dia_do_mes'] = df_diario.index.day
        df_diario['mes'] = df_diario.index.month
        df_diario['semana_do_ano'] = df_diario.index.isocalendar().week.astype(int)
        df_diario['evento_pagamento'] = df_diario['dia_do_mes'].isin(self.dias_de_evento['dia_pagamento']).astype(int)
        df_diario['evento_fim_de_mes'] = df_diario['dia_do_mes'].isin(self.dias_de_evento['fim_de_mes']).astype(int)
        df_diario['lag_1_dia_fluxo'] = df_diario['fluxo_diario'].shift(1).fillna(0)
        df_diario['media_movel_7d_fluxo'] = df_diario['fluxo_diario'].rolling(window=7, min_periods=1).mean().fillna(0)
        
        for cat in self.original_categories:
            if cat not in df_diario.columns:
                df_diario[cat] = 0
        
        df_diario = df_diario.reset_index()
        self.feature_columns = [col for col in df_diario.columns if col != 'fluxo_diario']
        
        return df_diario

    def train(self, df: pd.DataFrame):
        df_diario = self._extrair_features_avancado(df)
        
        X = df_diario[self.feature_columns].drop(columns=['data'])
        y = df_diario['fluxo_diario']

        if X.empty or len(X) < 2:
            print("Não há dados suficientes para treinar o modelo.")
            self.best_model_ = None
            return

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.15, random_state=42, shuffle=False)
        
        X_train.columns = X_train.columns.astype(str)
        X_test.columns = X_test.columns.astype(str)

        best_params = {'learning_rate': 0.1, 'max_depth': 3, 'n_estimators': 300, 'subsample': 0.7}
        self.model.set_params(**best_params)
        self.model.fit(X_train, y_train)
        self.best_model_ = self.model
        
        importances = self.best_model_.feature_importances_
        feature_names = X_train.columns
        
        feature_importance_df = pd.DataFrame({
            'feature': feature_names,
            'importance': importances
        }).sort_values(by='importance', ascending=False)
        
        state.global_feature_importance = feature_importance_df.to_dict(orient='records')

        preds = self.best_model_.predict(X_test)
        mae = mean_absolute_error(y_test, preds)
        print(f"\n--- AVALIAÇÃO DO MODELO TREINADO -> MAE: R$ {mae:.2f} ---\n")

    def predict(self, future_days: int, df_historico: pd.DataFrame) -> pd.DataFrame:
        if self.best_model_ is None:
            raise ValueError("O modelo ainda não foi treinado.")

        df_diario_historico = df_historico.set_index('data').resample('D').agg({'fluxo_diario': 'sum'}).fillna(0)

        if not df_diario_historico.empty:
            last_known_flow = df_diario_historico['fluxo_diario'].iloc[-1]
            initial_moving_avg = df_diario_historico['fluxo_diario'].rolling(window=7, min_periods=1).mean().iloc[-1]
        else:
            last_known_flow = 0
            initial_moving_avg = 0

        last_date = df_historico['data'].max() if not df_historico.empty else pd.Timestamp.now()
        future_dates = pd.to_datetime([last_date + pd.Timedelta(days=i) for i in range(1, future_days + 1)])
        
        future_df = pd.DataFrame(index=future_dates)
        
        future_df['dia_da_semana'] = future_df.index.dayofweek
        future_df['dia_do_mes'] = future_df.index.day
        future_df['mes'] = future_df.index.month
        future_df['semana_do_ano'] = future_df.index.isocalendar().week.astype(int)
        future_df['evento_pagamento'] = future_df['dia_do_mes'].isin(self.dias_de_evento['dia_pagamento']).astype(int)
        future_df['evento_fim_de_mes'] = future_df['dia_do_mes'].isin(self.dias_de_evento['fim_de_mes']).astype(int)
        
        for cat in self.original_categories:
            if cat not in future_df.columns:
                future_df[cat] = 0
            
        future_df['lag_1_dia_fluxo'] = last_known_flow
        future_df['media_movel_7d_fluxo'] = initial_moving_avg
        
        prediction_feature_columns = [col for col in self.feature_columns if col != 'data']
        X_future = future_df[prediction_feature_columns]
        X_future.columns = X_future.columns.astype(str)
        
        future_predictions = self.best_model_.predict(X_future)

        resultado_df = pd.DataFrame({
            'data': future_dates,
            'fluxo_previsto': future_predictions
        })
        
        ultimo_saldo = df_historico['saldo'].iloc[-1] if not df_historico.empty else 0
        resultado_df['saldo_previsto'] = ultimo_saldo + resultado_df['fluxo_previsto'].cumsum()

        return resultado_df[['data', 'fluxo_previsto', 'saldo_previsto']]

if __name__ == '__main__':
    pass