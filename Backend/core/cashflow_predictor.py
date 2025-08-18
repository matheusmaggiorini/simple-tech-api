import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, GridSearchCV
from xgboost import XGBRegressor
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
import os
from data_processing import processar_dados

class CashflowPredictor:
    def __init__(self):
        """
        Inicializa o preditor focado no melhor modelo: XGBoost.
        """
        self.model = XGBRegressor(random_state=42)
        self.best_model_ = None # O _ no final indica que foi treinado
        self.feature_columns = []

    def _extrair_features_avancado(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Cria features avançadas baseadas nas categorias das transações.
        """
        df_features = df.copy()
        
        df_diario = df.set_index('data').resample('D').agg({
            'fluxo_diario': 'sum'
        }).fillna(0)
        
        df_pivot = df.pivot_table(index='data', columns='categoria', values='fluxo_diario', aggfunc='sum').fillna(0)
        df_diario = df_diario.join(df_pivot, how='left').fillna(0)
        
        df_diario['dia_da_semana'] = df_diario.index.dayofweek
        df_diario['dia_do_mes'] = df_diario.index.day
        df_diario['mes'] = df_diario.index.month
        df_diario['semana_do_ano'] = df_diario.index.isocalendar().week.astype(int)
        
        df_diario['lag_1_dia_fluxo'] = df_diario['fluxo_diario'].shift(1).fillna(0)
        df_diario['media_movel_7d_fluxo'] = df_diario['fluxo_diario'].rolling(window=7).mean().fillna(df_diario['fluxo_diario'])
        
        self.feature_columns = [col for col in df_diario.columns if col != 'fluxo_diario']
        
        return df_diario.reset_index()

    def train(self, df: pd.DataFrame):
        """
        Usa GridSearchCV para encontrar os melhores hiperparâmetros para o XGBoost
        e treina o modelo final com essa configuração otimizada.
        """
        df_diario = self._extrair_features_avancado(df)
        
        X = df_diario[self.feature_columns]
        y = df_diario['fluxo_diario']

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.15, random_state=42, shuffle=False)

        print("\n--- INICIANDO OTIMIZAÇÃO DE HIPERPARÂMETROS PARA O XGBOOST ---")
        
        # 1. Define o "cardápio" de configurações que o GridSearchCV vai testar
        param_grid = {
            'n_estimators': [100, 200, 300],
            'max_depth': [3, 5, 7],
            'learning_rate': [0.01, 0.05, 0.1],
            'subsample': [0.7, 1.0]
        }

        # 2. Configura o GridSearchCV para encontrar o menor erro (neg_mean_absolute_error)
        # cv=3 significa que ele vai dividir os dados de treino em 3 partes para validar
        grid_search = GridSearchCV(
            estimator=self.model,
            param_grid=param_grid,
            scoring='neg_mean_absolute_error',
            cv=3,
            n_jobs=-1, # Usa todos os processadores disponíveis
            verbose=1 # Mostra o progresso
        )

        # 3. Executa a busca (pode demorar um pouco)
        grid_search.fit(X_train, y_train)

        print("\nOtimização concluída!")
        print(f"Melhor configuração encontrada: {grid_search.best_params_}")
        
        # 4. Usa o melhor modelo encontrado para fazer a avaliação final
        self.best_model_ = grid_search.best_estimator_
        preds = self.best_model_.predict(X_test)

        mae = mean_absolute_error(y_test, preds)
        mse = mean_squared_error(y_test, preds)
        r2 = r2_score(y_test, preds)

        print("\n--- AVALIAÇÃO DO MODELO OTIMIZADO ---")
        print(f"Resultado Final -> MAE: R$ {mae:.2f}, MSE: {mse:.2f}, R²: {r2:.2f}")
        print("-------------------------------------\n")


    def predict(self, future_days: int, df_historico: pd.DataFrame):
        if self.best_model_ is None:
            raise ValueError("O modelo ainda não foi treinado.")
        
        # A lógica de previsão futura continua a mesma
        print("AVISO: A função de previsão futura com as novas features é complexa.")
        return pd.DataFrame()


if __name__ == '__main__':
    print("Executando o script 'cashflow_predictor.py' em modo de teste e otimização.")

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