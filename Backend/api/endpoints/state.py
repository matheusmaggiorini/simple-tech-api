"""
Módulo para gerenciar o estado compartilhado entre os endpoints da API.
Este módulo centraliza as variáveis globais para evitar problemas de importação circular.
"""

import pandas as pd
from typing import Dict, Any, Optional

# Variáveis globais compartilhadas
global_processed_df: Optional[pd.DataFrame] = None
global_prediction_model: Any = None  # Armazenar o modelo treinado
global_historical_stats: Optional[Dict[str, Any]] = None

# Diretório para uploads temporários
UPLOAD_DIR = "data/api_uploads"

# Variável para armazenar o modelo de previsão treinado
global_prediction_model = None

# Variável para armazenar os resultados da análise de importância das features
global_feature_importance = None # <-- ADICIONE ESTA LINHA