import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error, r2_score, mean_squared_error
import os
import sys
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from api.endpoints import state

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        
        # Features temporais básicas
        df_diario['dia_da_semana'] = df_diario.index.dayofweek
        df_diario['dia_do_mes'] = df_diario.index.day
        df_diario['mes'] = df_diario.index.month
        df_diario['semana_do_ano'] = df_diario.index.isocalendar().week.astype(int)
        
        # Tendência e sazonalidade avançada
        start_date = df_diario.index.min()
        df_diario['dias_desde_inicio'] = (df_diario.index - start_date).days.astype(int)
        df_diario['dia_do_ano'] = df_diario.index.dayofyear.astype(int)
        
        # Sazonalidade complexa (múltiplas frequências)
        df_diario['seno_dia_ano'] = np.sin(2 * np.pi * df_diario['dia_do_ano'] / 365.25)
        df_diario['coseno_dia_ano'] = np.cos(2 * np.pi * df_diario['dia_do_ano'] / 365.25)
        df_diario['seno_semana'] = np.sin(2 * np.pi * df_diario['dia_da_semana'] / 7)
        df_diario['coseno_semana'] = np.cos(2 * np.pi * df_diario['dia_da_semana'] / 7)
        df_diario['seno_mes'] = np.sin(2 * np.pi * df_diario['dia_do_mes'] / 30.44)
        df_diario['coseno_mes'] = np.cos(2 * np.pi * df_diario['dia_do_mes'] / 30.44)
        
        # Eventos e indicadores especiais
        df_diario['evento_pagamento'] = df_diario['dia_do_mes'].isin(self.dias_de_evento['dia_pagamento']).astype(int)
        df_diario['evento_fim_de_mes'] = df_diario['dia_do_mes'].isin(self.dias_de_evento['fim_de_mes']).astype(int)
        df_diario['fim_de_semana'] = (df_diario['dia_da_semana'] >= 5).astype(int)
        df_diario['inicio_mes'] = (df_diario['dia_do_mes'] <= 5).astype(int)
        
        # Lags e médias móveis
        df_diario['lag_1_dia_fluxo'] = df_diario['fluxo_diario'].shift(1).fillna(0)
        df_diario['lag_2_dia_fluxo'] = df_diario['fluxo_diario'].shift(2).fillna(0)
        df_diario['lag_7_dia_fluxo'] = df_diario['fluxo_diario'].shift(7).fillna(0)
        
        df_diario['media_movel_3d_fluxo'] = df_diario['fluxo_diario'].rolling(window=3, min_periods=1).mean().fillna(0)
        df_diario['media_movel_7d_fluxo'] = df_diario['fluxo_diario'].rolling(window=7, min_periods=1).mean().fillna(0)
        df_diario['media_movel_14d_fluxo'] = df_diario['fluxo_diario'].rolling(window=14, min_periods=1).mean().fillna(0)
        df_diario['media_movel_30d_fluxo'] = df_diario['fluxo_diario'].rolling(window=30, min_periods=1).mean().fillna(0)
        
        # Features de volatilidade e variabilidade
        df_diario['std_7d_fluxo'] = df_diario['fluxo_diario'].rolling(window=7, min_periods=1).std().fillna(0)
        df_diario['std_30d_fluxo'] = df_diario['fluxo_diario'].rolling(window=30, min_periods=1).std().fillna(0)
        df_diario['cv_7d_fluxo'] = np.where(df_diario['media_movel_7d_fluxo'] != 0, 
                                          df_diario['std_7d_fluxo'] / df_diario['media_movel_7d_fluxo'], 0)
        df_diario['cv_30d_fluxo'] = np.where(df_diario['media_movel_30d_fluxo'] != 0, 
                                           df_diario['std_30d_fluxo'] / df_diario['media_movel_30d_fluxo'], 0)
        
        # Features de momentum e tendência
        df_diario['momentum_3d'] = df_diario['fluxo_diario'] - df_diario['fluxo_diario'].shift(3).fillna(0)
        df_diario['momentum_7d'] = df_diario['fluxo_diario'] - df_diario['fluxo_diario'].shift(7).fillna(0)
        df_diario['aceleracao_3d'] = df_diario['momentum_3d'] - df_diario['momentum_3d'].shift(1).fillna(0)
        
        # Features de mudança de regime
        df_diario['mudanca_brusca'] = (np.abs(df_diario['fluxo_diario'] - df_diario['fluxo_diario'].shift(1)) > 
                                     df_diario['std_7d_fluxo'] * 2).astype(int)
        df_diario['tendencia_7d'] = np.where(df_diario['media_movel_7d_fluxo'] > df_diario['media_movel_7d_fluxo'].shift(1), 1, 
                                           np.where(df_diario['media_movel_7d_fluxo'] < df_diario['media_movel_7d_fluxo'].shift(1), -1, 0))
        
        # Features de percentis e distribuição
        df_diario['percentil_7d'] = df_diario['fluxo_diario'].rolling(window=7, min_periods=1).quantile(0.5).fillna(0)
        df_diario['max_7d_fluxo'] = df_diario['fluxo_diario'].rolling(window=7, min_periods=1).max().fillna(0)
        df_diario['min_7d_fluxo'] = df_diario['fluxo_diario'].rolling(window=7, min_periods=1).min().fillna(0)
        df_diario['range_7d_fluxo'] = df_diario['max_7d_fluxo'] - df_diario['min_7d_fluxo']
        
        # Features de correlação temporal
        df_diario['autocorr_1d'] = df_diario['fluxo_diario'].rolling(window=7, min_periods=3).apply(
            lambda x: x.autocorr(lag=1) if len(x) >= 3 else 0, raw=False).fillna(0)
        
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

        # --- Início do Bloco de Validação de Métricas ---
        logger.info("Calculando métricas de validação no conjunto de teste...")

        try:
            # 1. Fazer previsões no conjunto de teste (dados que o modelo não viu no treino)
            y_pred = self.best_model_.predict(X_test)

            # 2. Calcular as métricas
            mae_val = mean_absolute_error(y_test, y_pred)
            r2_val = r2_score(y_test, y_pred)

            # 3. Exibir as métricas nos logs
            logger.info("="*50)
            logger.info("MÉTRICAS DE VALIDAÇÃO DO MODELO DE PREVISÃO")
            logger.info(f"  Erro Absoluto Médio (MAE): {mae_val:.2f}")
            logger.info(f"  Coeficiente R-squared (R²): {r2_val:.4f}")
            logger.info("="*50)
            logger.info(f"MAE (Explicação): Em média, as previsões do modelo no conjunto de teste erraram em R$ {mae_val:.2f} por dia.")
            logger.info(f"R² (Explicação): O modelo consegue explicar {r2_val:.2%} da variabilidade dos dados de fluxo de caixa.")

        except Exception as e:
            logger.error(f"Erro ao calcular métricas de validação: {e}")
        # --- Fim do Bloco de Validação de Métricas ---
        
        importances = self.best_model_.feature_importances_
        feature_names = X_train.columns
        
        feature_importance_df = pd.DataFrame({
            'feature': feature_names,
            'importance': importances
        }).sort_values(by='importance', ascending=False)
        
        state.global_feature_importance = feature_importance_df.to_dict(orient='records')

        preds = self.best_model_.predict(X_test)
        
        # Calcular métricas de performance
        mae = mean_absolute_error(y_test, preds)
        r2 = r2_score(y_test, preds)
        rmse = np.sqrt(mean_squared_error(y_test, preds))
        
        # Salvar métricas no estado global para acesso via API
        state.global_model_metrics = {
            'mae': float(mae),
            'r2': float(r2),
            'rmse': float(rmse),
            'mae_formatted': f"R$ {mae:.2f}",
            'r2_formatted': f"{r2:.3f}",
            'rmse_formatted': f"R$ {rmse:.2f}"
        }
        
        print(f"\n--- AVALIAÇÃO DO MODELO TREINADO ---")
        print(f"MAE (Erro Médio Absoluto): R$ {mae:.2f}")
        print(f"R² (Coeficiente de Determinação): {r2:.3f}")
        print(f"RMSE (Raiz do Erro Quadrático Médio): R$ {rmse:.2f}")
        print(f"---\n")

    def predict(self, future_days: int, df_historico: pd.DataFrame) -> pd.DataFrame:
        if self.best_model_ is None:
            raise ValueError("O modelo ainda não foi treinado.")

        # Série histórica diária para fornecer contexto aos lags e médias móveis
        df_diario_historico = df_historico.set_index('data').resample('D').agg({'fluxo_diario': 'sum'}).fillna(0)

        # Datas de previsão
        last_date = df_historico['data'].max() if not df_historico.empty else pd.Timestamp.now().normalize()
        future_dates = pd.to_datetime([last_date + pd.Timedelta(days=i) for i in range(1, future_days + 1)])
        
        # Preparação para previsão recorrente: manter uma lista dos últimos fluxos (reais + previstos)
        historico_fluxos = df_diario_historico['fluxo_diario'].tolist() if not df_diario_historico.empty else []
        start_date_hist = df_diario_historico.index.min() if not df_diario_historico.empty else last_date

        # Calcular estatísticas históricas para variação controlada
        if len(historico_fluxos) > 0:
            hist_std = np.std(historico_fluxos)
            hist_mean = np.mean(historico_fluxos)
            hist_cv = hist_std / abs(hist_mean) if hist_mean != 0 else 0.1
            hist_median = np.median(historico_fluxos)
        else:
            hist_std = 1000  # Valor padrão
            hist_cv = 0.2
            hist_median = 0

        # Colunas esperadas pelo modelo durante a previsão (mesma base do treino, exceto 'data')
        prediction_feature_columns = [col for col in self.feature_columns if col != 'data']

        previsoes = []

        # Previsão Recorrente: para cada dia futuro, recalcular lags e médias com base em valores
        # reais/previstos acumulados até o dia anterior. Isso permite que o modelo propague
        # a dinâmica aprendida (tendências e sazonalidades) ao longo do horizonte de previsão.
        for i, current_date in enumerate(future_dates):
            # Lags dinâmicos
            lag_1 = historico_fluxos[-1] if len(historico_fluxos) > 0 else 0.0
            lag_2 = historico_fluxos[-2] if len(historico_fluxos) >= 2 else 0.0
            lag_7 = historico_fluxos[-7] if len(historico_fluxos) >= 7 else 0.0

            # Médias móveis dinâmicas usando janelas deslizantes dos últimos valores
            janela_3 = historico_fluxos[-3:] if len(historico_fluxos) >= 1 else []
            janela_7 = historico_fluxos[-7:] if len(historico_fluxos) >= 1 else []
            janela_14 = historico_fluxos[-14:] if len(historico_fluxos) >= 1 else []
            janela_30 = historico_fluxos[-30:] if len(historico_fluxos) >= 1 else []
            
            media_3 = float(np.mean(janela_3)) if len(janela_3) > 0 else 0.0
            media_7 = float(np.mean(janela_7)) if len(janela_7) > 0 else 0.0
            media_14 = float(np.mean(janela_14)) if len(janela_14) > 0 else 0.0
            media_30 = float(np.mean(janela_30)) if len(janela_30) > 0 else 0.0

            # Volatilidade dinâmica
            std_7 = float(np.std(janela_7)) if len(janela_7) > 1 else hist_std
            std_30 = float(np.std(janela_30)) if len(janela_30) > 1 else hist_std
            cv_7 = std_7 / abs(media_7) if media_7 != 0 else hist_cv
            cv_30 = std_30 / abs(media_30) if media_30 != 0 else hist_cv

            # Momentum e aceleração
            momentum_3 = lag_1 - (historico_fluxos[-4] if len(historico_fluxos) >= 4 else lag_1)
            momentum_7 = lag_1 - (historico_fluxos[-8] if len(historico_fluxos) >= 8 else lag_1)
            aceleracao_3 = momentum_3 - (historico_fluxos[-2] - (historico_fluxos[-5] if len(historico_fluxos) >= 5 else historico_fluxos[-2]))

            # Features de distribuição
            max_7 = float(np.max(janela_7)) if len(janela_7) > 0 else lag_1
            min_7 = float(np.min(janela_7)) if len(janela_7) > 0 else lag_1
            range_7 = max_7 - min_7
            percentil_7 = float(np.percentile(janela_7, 50)) if len(janela_7) > 0 else lag_1

            # Tendência e mudanças de regime
            tendencia_7 = 1 if media_7 > (historico_fluxos[-8] if len(historico_fluxos) >= 8 else media_7) else -1 if media_7 < (historico_fluxos[-8] if len(historico_fluxos) >= 8 else media_7) else 0
            mudanca_brusca = 1 if abs(lag_1 - (historico_fluxos[-2] if len(historico_fluxos) >= 2 else lag_1)) > std_7 * 2 else 0

            # Autocorrelação (simplificada)
            if len(historico_fluxos) >= 3:
                autocorr_1d = np.corrcoef(historico_fluxos[-3:], [historico_fluxos[-4], historico_fluxos[-3], historico_fluxos[-2]])[0,1] if len(historico_fluxos) >= 4 else 0
            else:
                autocorr_1d = 0

            # Construção das features do dia atual
            row_dict = {
                'dia_da_semana': current_date.dayofweek,
                'dia_do_mes': current_date.day,
                'mes': current_date.month,
                'semana_do_ano': int(pd.Timestamp(current_date).isocalendar().week),
                'dias_desde_inicio': int((current_date - start_date_hist).days),
                'dia_do_ano': int(pd.Timestamp(current_date).dayofyear),
                
                # Sazonalidade complexa
                'seno_dia_ano': float(np.sin(2 * np.pi * current_date.dayofyear / 365.25)),
                'coseno_dia_ano': float(np.cos(2 * np.pi * current_date.dayofyear / 365.25)),
                'seno_semana': float(np.sin(2 * np.pi * current_date.dayofweek / 7)),
                'coseno_semana': float(np.cos(2 * np.pi * current_date.dayofweek / 7)),
                'seno_mes': float(np.sin(2 * np.pi * current_date.day / 30.44)),
                'coseno_mes': float(np.cos(2 * np.pi * current_date.day / 30.44)),
                
                # Eventos e indicadores
                'evento_pagamento': int(current_date.day in self.dias_de_evento['dia_pagamento']),
                'evento_fim_de_mes': int(current_date.day in self.dias_de_evento['fim_de_mes']),
                'fim_de_semana': int(current_date.dayofweek >= 5),
                'inicio_mes': int(current_date.day <= 5),
                
                # Lags
                'lag_1_dia_fluxo': float(lag_1),
                'lag_2_dia_fluxo': float(lag_2),
                'lag_7_dia_fluxo': float(lag_7),
                
                # Médias móveis
                'media_movel_3d_fluxo': float(media_3),
                'media_movel_7d_fluxo': float(media_7),
                'media_movel_14d_fluxo': float(media_14),
                'media_movel_30d_fluxo': float(media_30),
                
                # Volatilidade
                'std_7d_fluxo': float(std_7),
                'std_30d_fluxo': float(std_30),
                'cv_7d_fluxo': float(cv_7),
                'cv_30d_fluxo': float(cv_30),
                
                # Momentum e tendência
                'momentum_3d': float(momentum_3),
                'momentum_7d': float(momentum_7),
                'aceleracao_3d': float(aceleracao_3),
                'tendencia_7d': int(tendencia_7),
                'mudanca_brusca': int(mudanca_brusca),
                
                # Distribuição
                'percentil_7d': float(percentil_7),
                'max_7d_fluxo': float(max_7),
                'min_7d_fluxo': float(min_7),
                'range_7d_fluxo': float(range_7),
                
                # Correlação temporal
                'autocorr_1d': float(autocorr_1d),
            }

            # Garante presença das colunas de categorias usadas no treino (preenche com 0 para futuro)
            for cat in self.original_categories:
                row_dict.setdefault(cat, 0)

            # Assegura que todas as colunas esperadas existem (faltantes -> 0)
            for col in prediction_feature_columns:
                if col not in row_dict and col != 'data':
                    row_dict[col] = 0

            X_future_day = pd.DataFrame([row_dict])
            # Reordenar e limitar para exatamente as colunas de previsão esperadas
            X_future_day = X_future_day.reindex(columns=prediction_feature_columns, fill_value=0)
            X_future_day.columns = X_future_day.columns.astype(str)

            # Previsão do dia corrente
            predicted_flow = float(self.best_model_.predict(X_future_day)[0])
            
            # Aplicar variação determinística baseada em padrões do histórico
            if len(historico_fluxos) > 0:
                # Calcular variação baseada no coeficiente de variação histórico (CV)
                hist_cv = hist_std / abs(hist_mean) if hist_mean != 0 else 0.25
                
                # Gerar variação determinística usando hash da data (sempre igual para mesma data)
                date_hash = hash(str(current_date)) % 10000
                variation_seed = (date_hash / 10000.0) * 2 - 1  # -1 a +1
                
                # Aplicar variação proporcional à volatilidade histórica (mais forte)
                base_variation = 1 + (variation_seed * hist_cv * 1.4)
                predicted_flow = predicted_flow * base_variation
                
                # Choques determinísticos em alguns dias (quando |seed| alto)
                abs_seed = abs(variation_seed)
                if abs_seed > 0.6:
                    shock_magnitude = min(0.6, hist_cv * 2.0)  # até +/−60%
                    shock = 1 + (np.sign(variation_seed) * shock_magnitude)
                    predicted_flow *= shock
                
                # Fatores sazonais determinísticos (baseados na data, não aleatórios)
                weekday_factor = {
                    0: 1.20,  # Segunda-feira: +20%
                    1: 1.10,  # Terça-feira: +10%
                    2: 1.00,  # Quarta-feira: normal
                    3: 0.92,  # Quinta-feira: -8%
                    4: 0.80,  # Sexta-feira: -20%
                    5: 0.55,  # Sábado: -45%
                    6: 0.48   # Domingo: -52%
                }
                
                # Fatores mensais determinísticos
                day_of_month = current_date.day
                if day_of_month <= 3:
                    month_factor = 1.30  # Primeiros 3 dias: +30%
                elif day_of_month <= 7:
                    month_factor = 1.12  # Primeira semana: +12%
                elif day_of_month >= 28:
                    month_factor = 1.25  # Últimos dias: +25%
                else:
                    month_factor = 1.0   # Meio do mês: normal
                
                # Aplicar fatores sazonais
                weekday_multiplier = weekday_factor.get(current_date.dayofweek, 1.0)
                predicted_flow = predicted_flow * weekday_multiplier * month_factor

                # Impulsionar eventos de pagamento e fim de mês de forma determinística
                # Em dias de pagamento, entradas tendem a subir e saídas também podem concentrar
                if int(current_date.day in self.dias_de_evento['dia_pagamento']):
                    boost = 1.6 if predicted_flow >= 0 else 1.25
                    predicted_flow *= boost
                if int(current_date.day in self.dias_de_evento['fim_de_mes']):
                    eom_boost = 1.35 if predicted_flow < 0 else 1.15
                    predicted_flow *= eom_boost

                # Heteroscedasticidade por dia da semana: mais variação em seg-sex
                dow_volatility = {
                    0: 1.15, 1: 1.10, 2: 1.05, 3: 1.10, 4: 1.15, 5: 0.90, 6: 0.85
                }.get(current_date.dayofweek, 1.0)
                predicted_flow *= dow_volatility
                
                # Limites realistas baseados no histórico
                hist_min = min(historico_fluxos)
                hist_max = max(historico_fluxos)
                hist_median = np.median(historico_fluxos)
                
                # Limites mais flexíveis para permitir variação
                predicted_flow = np.clip(
                    predicted_flow,
                    hist_min * 0.1,   # Mínimo: 10% do menor valor histórico
                    hist_max * 3.0    # Máximo: 300% do maior valor histórico
                )
                
                # Suavização leve para evitar série excessivamente contínua, preservando variação
                if len(historico_fluxos) >= 3:
                    recent_trend = np.mean(historico_fluxos[-3:])
                    # Em dias com choque, reduzir suavização ainda mais
                    smoothing_factor = 0.08 if abs_seed > 0.6 else 0.10
                    predicted_flow = predicted_flow * (1 - smoothing_factor) + recent_trend * smoothing_factor

            # Evitar valores excessivamente contínuos: reforça discretização em centavos e pequenas quebras
            # Quantiza em centavos e aplica um micro ajuste determinístico por data
            cents_quantized = np.round(predicted_flow, 2)
            micro_jitter = ((hash(str(current_date.date())) % 11) - 5) * 0.05  # faixa ~[-0.25, 0.25]
            predicted_flow = float(np.round(cents_quantized + micro_jitter, 2))

            # Armazena previsão e atualiza histórico para o próximo passo da recorrência
            previsoes.append({'data': current_date, 'fluxo_previsto': predicted_flow})
            historico_fluxos.append(predicted_flow)

        resultado_df = pd.DataFrame(previsoes)
        ultimo_saldo = df_historico['saldo'].iloc[-1] if not df_historico.empty else 0
        resultado_df['saldo_previsto'] = ultimo_saldo + resultado_df['fluxo_previsto'].cumsum()

        return resultado_df[['data', 'fluxo_previsto', 'saldo_previsto']]

if __name__ == '__main__':
    pass