"""
Módulos mock para simular a funcionalidade dos módulos core
Este arquivo deve ser usado temporariamente até que os módulos reais sejam implementados
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataProcessingMock:
    """Mock para o módulo data_processing"""
    
    @staticmethod
    def processar_arquivo_completo(file_path: str) -> Optional[pd.DataFrame]:
        """
        Processa um arquivo CSV e retorna um DataFrame formatado
        """
        try:
            # Ler o arquivo CSV
            df = pd.read_csv(file_path)
            
            # Validar colunas obrigatórias
            required_columns = ['data', 'descricao', 'entrada', 'saida']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                logger.error(f"Colunas obrigatórias ausentes: {missing_columns}")
                return None
            
            # Converter coluna de data
            df['data'] = pd.to_datetime(df['data'])
            
            # Garantir que entrada e saida são numéricas
            df['entrada'] = pd.to_numeric(df['entrada'], errors='coerce').fillna(0)
            df['saida'] = pd.to_numeric(df['saida'], errors='coerce').fillna(0)
            
            # Calcular saldo
            df['saldo'] = (df['entrada'] - df['saida']).cumsum()
            
            # Ordenar por data
            df = df.sort_values('data').reset_index(drop=True)
            
            logger.info(f"Arquivo processado com sucesso: {len(df)} registros")
            return df
            
        except Exception as e:
            logger.error(f"Erro ao processar arquivo: {str(e)}")
            return None

class CashflowPredictorMock:
    """Mock para o módulo cashflow_predictor"""
    
    @staticmethod
    def preparar_dados_para_regressao(df: pd.DataFrame, dias_para_prever: int = 7) -> Optional[Tuple]:
        """
        Prepara dados para treinamento do modelo de regressão
        """
        try:
            if len(df) < dias_para_prever + 1:
                return None
            
            # Criar features simples (últimos N dias de entrada/saída)
            features = []
            targets = []
            
            for i in range(len(df) - dias_para_prever):
                # Features: entrada e saída dos últimos dias_para_prever dias
                feature_window = df.iloc[i:i+dias_para_prever]
                feature_vector = [
                    feature_window['entrada'].sum(),
                    feature_window['saida'].sum(),
                    feature_window['entrada'].mean(),
                    feature_window['saida'].mean()
                ]
                features.append(feature_vector)
                
                # Target: saldo após os próximos dias
                targets.append(df.iloc[i + dias_para_prever]['saldo'])
            
            return np.array(features), np.array(targets)
            
        except Exception as e:
            logger.error(f"Erro ao preparar dados: {str(e)}")
            return None
    
    @staticmethod
    def treinar_modelo_regressao(X: np.ndarray, y: np.ndarray):
        """
        Treina um modelo de regressão simples
        """
        try:
            # Modelo mock simples (média móvel)
            class SimpleModel:
                def __init__(self, X, y):
                    self.mean_target = np.mean(y)
                    self.trend = (y[-1] - y[0]) / len(y) if len(y) > 1 else 0
                
                def predict(self, X_new):
                    # Previsão simples baseada na tendência
                    return [self.mean_target + self.trend * i for i in range(len(X_new))]
            
            return SimpleModel(X, y)
            
        except Exception as e:
            logger.error(f"Erro ao treinar modelo: {str(e)}")
            return None
    
    @staticmethod
    def gerar_previsao_com_regressao(modelo, df: pd.DataFrame, dias_a_prever: int = 30, dias_para_target: int = 7):
        """
        Gera previsões usando o modelo treinado
        """
        try:
            # Criar datas futuras
            last_date = df['data'].max()
            future_dates = [last_date + timedelta(days=i+1) for i in range(dias_a_prever)]
            
            # Gerar previsões mock
            last_saldo = df['saldo'].iloc[-1]
            avg_entrada = df['entrada'].mean()
            avg_saida = df['saida'].mean()
            daily_change = avg_entrada - avg_saida
            
            predictions = []
            current_saldo = last_saldo
            
            for i, date in enumerate(future_dates):
                # Adicionar alguma variabilidade
                daily_entrada = avg_entrada * (1 + np.random.normal(0, 0.1))
                daily_saida = avg_saida * (1 + np.random.normal(0, 0.1))
                current_saldo += daily_entrada - daily_saida
                
                predictions.append({
                    'data': date,
                    'entrada_prevista': max(0, daily_entrada),
                    'saida_prevista': max(0, daily_saida),
                    'saldo_previsto': current_saldo
                })
            
            return pd.DataFrame(predictions)
            
        except Exception as e:
            logger.error(f"Erro ao gerar previsões: {str(e)}")
            return pd.DataFrame()

class RiskAnalyzerMock:
    """Mock para o módulo risk_analyzer"""
    
    @staticmethod
    def identificar_riscos_com_base_em_limiares(df_previsoes: pd.DataFrame, saldo_inicial: float) -> List[Dict]:
        """
        Identifica riscos nas previsões
        """
        try:
            alertas = []
            
            # Verificar saldo negativo
            saldos_negativos = df_previsoes[df_previsoes['saldo_previsto'] < 0]
            if not saldos_negativos.empty:
                primeiro_negativo = saldos_negativos.iloc[0]
                alertas.append({
                    'tipo': 'saldo_negativo',
                    'severidade': 'alta',
                    'data': primeiro_negativo['data'].strftime('%Y-%m-%d'),
                    'valor': primeiro_negativo['saldo_previsto'],
                    'mensagem': f"Saldo previsto ficará negativo em {primeiro_negativo['data'].strftime('%Y-%m-%d')}"
                })
            
            # Verificar queda significativa no saldo
            if len(df_previsoes) > 0:
                saldo_final = df_previsoes['saldo_previsto'].iloc[-1]
                if saldo_final < saldo_inicial * 0.5:  # Queda de mais de 50%
                    alertas.append({
                        'tipo': 'queda_significativa',
                        'severidade': 'media',
                        'data': df_previsoes['data'].iloc[-1].strftime('%Y-%m-%d'),
                        'valor': saldo_final,
                        'mensagem': f"Saldo previsto cairá mais de 50% até {df_previsoes['data'].iloc[-1].strftime('%Y-%m-%d')}"
                    })
            
            return alertas
            
        except Exception as e:
            logger.error(f"Erro ao analisar riscos: {str(e)}")
            return []

class ScenarioSimulatorMock:
    """Mock para o módulo scenario_simulator"""
    
    @staticmethod
    def calcular_estatisticas_historicas(df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calcula estatísticas históricas dos dados
        """
        try:
            return {
                'entrada_media': df['entrada'].mean(),
                'entrada_std': df['entrada'].std(),
                'saida_media': df['saida'].mean(),
                'saida_std': df['saida'].std(),
                'saldo_atual': df['saldo'].iloc[-1] if not df.empty else 0,
                'periodo_dias': len(df)
            }
        except Exception as e:
            logger.error(f"Erro ao calcular estatísticas: {str(e)}")
            return {}
    
    @staticmethod
    def gerar_parametros_simulacao(stats: Dict, variacao_entrada: float = 0.1, 
                                 variacao_saida: float = 0.1, dias_simulacao: int = 30,
                                 num_simulacoes: int = 100, saldo_inicial: Optional[float] = None):
        """
        Gera parâmetros para simulação Monte Carlo
        """
        return {
            'entrada_media': stats.get('entrada_media', 0),
            'entrada_std': stats.get('entrada_std', 0) * (1 + variacao_entrada),
            'saida_media': stats.get('saida_media', 0),
            'saida_std': stats.get('saida_std', 0) * (1 + variacao_saida),
            'saldo_inicial': saldo_inicial or stats.get('saldo_atual', 0),
            'dias_simulacao': dias_simulacao,
            'num_simulacoes': num_simulacoes
        }
    
    @staticmethod
    def executar_simulacao_monte_carlo(parametros: Dict):
        """
        Executa simulação Monte Carlo
        """
        try:
            resultados = []
            num_sim = parametros['num_simulacoes']
            dias = parametros['dias_simulacao']
            saldo_inicial = parametros['saldo_inicial']
            
            for sim in range(num_sim):
                saldo_atual = saldo_inicial
                for dia in range(dias):
                    entrada = max(0, np.random.normal(parametros['entrada_media'], parametros['entrada_std']))
                    saida = max(0, np.random.normal(parametros['saida_media'], parametros['saida_std']))
                    saldo_atual += entrada - saida
                
                resultados.append({
                    'simulacao': sim,
                    'saldo_final': saldo_atual,
                    'dias': dias
                })
            
            df_resultados = pd.DataFrame(resultados)
            return df_resultados, parametros
            
        except Exception as e:
            logger.error(f"Erro na simulação: {str(e)}")
            return pd.DataFrame(), parametros
    
    @staticmethod
    def analisar_probabilidades(df_resultados: pd.DataFrame) -> Dict[str, Any]:
        """
        Analisa probabilidades dos resultados da simulação
        """
        try:
            if df_resultados.empty:
                return {}
            
            saldos = df_resultados['saldo_final']
            
            return {
                'saldo_medio': float(saldos.mean()),
                'saldo_mediano': float(saldos.median()),
                'saldo_std': float(saldos.std()),
                'saldo_min': float(saldos.min()),
                'saldo_max': float(saldos.max()),
                'prob_saldo_negativo': float((saldos < 0).mean()),
                'percentil_25': float(saldos.quantile(0.25)),  # Cenário pessimista
                'percentil_50': float(saldos.quantile(0.50)),  # Cenário mais provável
                'percentil_75': float(saldos.quantile(0.75)),  # Cenário otimista
                'num_simulacoes': len(df_resultados)
            }
            
        except Exception as e:
            logger.error(f"Erro ao analisar probabilidades: {str(e)}")
            return {}

# Instanciar os mocks para simular os módulos
data_processing = DataProcessingMock()
cashflow_predictor = CashflowPredictorMock()
risk_analyzer = RiskAnalyzerMock()
scenario_simulator = ScenarioSimulatorMock()