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
global_cycle_metrics: Optional[Dict[str, Any]] = None  # Armazenar os prazos médios
global_feature_importance: Optional[Any] = None  # Armazenar importância das features

# Diretório para uploads temporários
UPLOAD_DIR = "data/api_uploads"

