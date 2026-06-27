from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, field_validator, model_validator
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List
import sys
import os
import traceback
import logging

# Configurar logging para debug
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Importar o estado compartilhado e os simuladores de cenários
from api.endpoints import state
from api.core.deps import get_current_user
# Importa AMBAS as funções de simulação do módulo atualizado
from core.scenario_simulator import run_simulation, run_event_simulation, run_loan_simulation
from core.loan_analyzer import suggest_loan_options
# Importa a nova função para analisar eventos de negócio
from core.business_event_analyzer import identify_key_business_events
# Importa a função para processar dados
from core.data_processing import processar_dados

# Definir o router
router = APIRouter()

# --- Modelos Pydantic Atualizados ---

class SeasonalityRule(BaseModel):
    """Modelo para regras de sazonalidade (usado na simulação macro)."""
    month: str
    revenue_change_percentage: float

class EventModifier(BaseModel):
    """Modelo para um modificador de evento de negócio."""
    name: str
    value_change_percentage: float = 0.0
    delay_days: int = 0

class SimulationRequest(BaseModel):
    """Modelo de requisição unificado para ambos os tipos de simulação."""
    simulation_type: str = "macroeconomic"  # 'macroeconomic' ou 'event' ou 'loan_impact'
    
    # Parâmetros para simulação macroeconômica
    scenario_type: Optional[str] = None
    seasonality_rules: Optional[List[SeasonalityRule]] = None
    
    # Parâmetros para simulação de eventos
    inflow_modifiers: Optional[List[EventModifier]] = None
    outflow_modifiers: Optional[List[EventModifier]] = None

    # Parâmetros para simulação de empréstimo
    loan_params: Optional['LoanParams'] = None

    @model_validator(mode='after')
    def validate_macroeconomic_requirements(self):
        if self.simulation_type == 'macroeconomic':
            if not self.scenario_type:
                raise ValueError('scenario_type é obrigatório para a simulação macroeconômica.')
            if self.scenario_type not in ['otimista', 'mais_provavel', 'pessimista', 'conservador']:
                raise ValueError(f'Tipo de cenário inválido: {self.scenario_type}. Use otimista, mais_provavel ou pessimista.')
        return self

class LoanParams(BaseModel):
    amount: float
    interest_rate_monthly: float
    term_months: int

    @field_validator('amount', mode='before')
    def parse_amount(cls, v):
        if isinstance(v, str):
            v = v.replace('\u00A0', '').replace(' ', '').replace('.', '').replace(',', '.')
        try:
            return float(v)
        except Exception:
            raise ValueError('amount inválido')

    @field_validator('interest_rate_monthly', mode='before')
    def parse_rate(cls, v):
        if isinstance(v, str):
            v = v.replace('\u00A0', '').replace(' ', '').replace('.', '').replace(',', '.')
        try:
            return float(v)
        except Exception:
            raise ValueError('interest_rate_monthly inválido')

    @field_validator('term_months', mode='before')
    def parse_term(cls, v):
        if isinstance(v, str):
            v = v.strip()
            v = v.replace('\u00A0', '').replace(' ', '')
            v = v.replace('.', '').replace(',', '.')
            try:
                v = float(v)
            except Exception:
                raise ValueError('term_months inválido')
        try:
            return int(round(v))
        except Exception:
            raise ValueError('term_months inválido')

    
class LoanSimulationResponse(BaseModel):
    scenario_type: str
    original_summary: Dict[str, Any]
    simulated_summary: Dict[str, Any]
    monthly_details: List[Dict[str, Any]]

class LoanSuggestionResponse(BaseModel):
    sos_loan: Dict[str, Any]
    strategic_loan: Dict[str, Any]

class SimulationResponse(BaseModel):
    """Modelo para resposta da simulação."""
    scenario_type: str
    original_summary: Dict[str, Any]
    simulated_summary: Dict[str, Any]
    monthly_details: List[Dict[str, Any]]
    # Compatibilidade com frontend que espera 'results_summary'
    results_summary: Optional[Dict[str, Any]] = None
    # Compatibilidade com frontend que espera 'scenarios.pessimista/mais_provavel/otimista'
    scenarios: Optional[Dict[str, Any]] = None

# --- Funções Auxiliares ---

def calculate_dataframe_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """Calcula um resumo estatístico do DataFrame de previsão."""
    try:
        # Garante que as colunas existam e sejam numéricas
        required_columns = ['receita_total', 'custo_total', 'fluxo_de_caixa']
        for col in required_columns:
            if col not in df.columns:
                df[col] = 0.0
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        summary = {
            "total_receita": float(df['receita_total'].sum()),
            "total_custo": float(df['custo_total'].sum()),
            "total_fluxo_de_caixa": float(df['fluxo_de_caixa'].sum()),
            "meses_com_fluxo_positivo": int((df['fluxo_de_caixa'] > 0).sum()),
            "meses_com_fluxo_negativo": int((df['fluxo_de_caixa'] < 0).sum()),
            # Campos adicionais esperados pelo frontend
            "media_mensal_fluxo": float(df['fluxo_de_caixa'].mean()) if len(df) > 0 else 0.0,
            "menor_fluxo_mensal": float(df['fluxo_de_caixa'].min()) if len(df) > 0 else 0.0,
            "maior_fluxo_mensal": float(df['fluxo_de_caixa'].max()) if len(df) > 0 else 0.0,
        }
        return summary
    except Exception as e:
        logger.error(f"Erro ao calcular resumo do DataFrame: {str(e)}")
        # Retorna resumo padrão em caso de erro
        return {
            "total_receita": 0.0,
            "total_custo": 0.0,
            "total_fluxo_de_caixa": 0.0,
            "meses_com_fluxo_positivo": 0,
            "meses_com_fluxo_negativo": 0,
            "media_mensal_fluxo": 0.0,
            "menor_fluxo_mensal": 0.0,
            "maior_fluxo_mensal": 0.0,
        }

def convert_dataframe_to_monthly_details(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Converte o DataFrame em uma lista de detalhes mensais para o frontend."""
    try:
        df_copy = df.copy()
        # Garante que não há valores NaN que causem problemas no JSON
        for col in ['receita_total', 'custo_total', 'fluxo_de_caixa']:
            if col in df_copy.columns:
                df_copy[col] = pd.to_numeric(df_copy[col], errors='coerce').fillna(0)
        
        return df_copy.to_dict(orient="records")
    except Exception as e:
        logger.error(f"Erro ao converter DataFrame para lista: {str(e)}")
        return []

def create_mock_forecast_data(months: int = 12) -> pd.DataFrame:
    """Cria dados de previsão mock para teste quando não há dados reais."""
    logger.info("⚠️  Criando dados mock para demonstração da simulação")
    
    month_names = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 
                   'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
    
    mock_data = []
    for i in range(months):
        month_name = month_names[i % 12]
        base_revenue = 10000 + (i * 1000)  # Crescimento gradual
        base_cost = 8000 + (i * 500)       # Crescimento gradual dos custos
        
        mock_data.append({
            'mes': month_name,
            'receita_total': base_revenue,
            'custo_total': base_cost,
            'fluxo_de_caixa': base_revenue - base_cost
        })
    
    return pd.DataFrame(mock_data)

def create_mock_historical_data(days: int = 180) -> pd.DataFrame:
    """Cria dados históricos mock para simulação de eventos."""
    logger.info("⚠️  Criando dados históricos mock para simulação de eventos")
    
    np.random.seed(42)  # Para resultados consistentes
    
    # Clientes/fornecedores mock
    clientes = ['Cliente A', 'Cliente B', 'Cliente C', 'Vendas Online', 'Produto X']
    fornecedores = ['Fornecedor 1', 'Fornecedor 2', 'Aluguel', 'Salários', 'Energia']
    
    mock_data = []
    start_date = pd.Timestamp.now() - pd.DateOffset(days=days)
    
    for i in range(days):
        current_date = start_date + pd.DateOffset(days=i)
        
        # Simula transações diárias (nem todo dia tem movimento)
        if np.random.random() > 0.3:  # 70% de chance de ter movimento
            
            # Entradas (receitas)
            if np.random.random() > 0.4:  # 60% de chance de entrada
                cliente = np.random.choice(clientes)
                valor_entrada = np.random.uniform(500, 5000)
                mock_data.append({
                    'data': current_date,
                    'descricao': cliente,
                    'categoria': 'Receita',
                    'entrada': valor_entrada,
                    'saida': 0.0,
                    'saldo': 0.0  # Será calculado depois
                })
            
            # Saídas (custos)
            if np.random.random() > 0.5:  # 50% de chance de saída
                fornecedor = np.random.choice(fornecedores)
                valor_saida = np.random.uniform(200, 3000)
                mock_data.append({
                    'data': current_date,
                    'descricao': fornecedor,
                    'categoria': 'Despesa',
                    'entrada': 0.0,
                    'saida': valor_saida,
                    'saldo': 0.0  # Será calculado depois
                })
    
    df = pd.DataFrame(mock_data)
    
    if not df.empty:
        # Calcula o saldo acumulado
        df = df.sort_values('data')
        df['saldo'] = (df['entrada'] - df['saida']).cumsum()
    
    return df
# --- Novos Endpoints de Empréstimo ---

def _user_df(user: dict) -> pd.DataFrame | None:
    return state.get_user_session(user["id"]).processed_df


def _historical_df(user: dict) -> pd.DataFrame:
    df = _user_df(user)
    if df is None or df.empty:
        return create_mock_historical_data(180)
    return df.copy()


@router.get("/loan-suggestions")
async def get_loan_suggestions(user: dict = Depends(get_current_user)):
    try:
        historical_df = _historical_df(user)
        suggestions = suggest_loan_options(historical_df)
        return suggestions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def validate_historical_data_for_events(df: pd.DataFrame) -> bool:
    """Valida se o DataFrame histórico tem as colunas necessárias para simulação de eventos."""
    required_columns = ['data', 'descricao', 'entrada', 'saida']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        raise ValueError(f"DataFrame histórico deve conter as colunas: {', '.join(missing_columns)}")
    
    # Tenta converter a coluna data
    try:
        df['data'] = pd.to_datetime(df['data'])
    except Exception as e:
        raise ValueError(f"Erro ao converter coluna 'data': {str(e)}")
    
    return True

# --- Função para carregar dados reais das planilhas de saída ---

def load_real_business_data():
    """
    Carrega dados reais das planilhas de saída e entrada localizadas em Backend/data/
    """
    try:
        import pandas as pd
        from pathlib import Path
        
        # Caminho para as planilhas de saída
        outflow_dir = Path("Backend/data/dados_de_saida")
        
        # Caminho para as planilhas de entrada (se existirem)
        inflow_dir = Path("Backend/data")
        
        all_data = []
        files_loaded = []
        
        # Carregar planilhas de saída
        if outflow_dir.exists():
            logger.info(f"Carregando planilhas de saída de: {outflow_dir}")
            for file_path in outflow_dir.glob("*.xlsx"):
                try:
                    logger.info(f"Carregando planilha de saída: {file_path.name}")
                    df = pd.read_excel(file_path)
                    
                    # Verificar se tem as colunas necessárias
                    required_cols = ['SAIDA', 'VALOR', 'DATA']
                    missing_cols = [col for col in required_cols if col not in df.columns]
                    
                    if missing_cols:
                        logger.warning(f"Planilha {file_path.name} não tem colunas: {missing_cols}")
                        continue
                    
                    # Adicionar nome do arquivo para debug
                    df['arquivo_origem'] = file_path.name
                    df['tipo_transacao'] = 'saida'
                    all_data.append(df)
                    files_loaded.append(f"SAIDA: {file_path.name}")
                    
                except Exception as e:
                    logger.error(f"Erro ao carregar {file_path.name}: {str(e)}")
                    continue
        
        # Carregar planilhas de entrada (se existirem)
        if inflow_dir.exists():
            logger.info(f"Procurando planilhas de entrada em: {inflow_dir}")
            
            # Carregar planilha principal que contém receitas e custos
            main_file = inflow_dir / "base_de_dados_empresa_longa.xlsx"
            if main_file.exists():
                try:
                    logger.info(f"Carregando planilha principal: {main_file.name}")
                    df = pd.read_excel(main_file)
                    
                    # Verificar se tem colunas de entrada e saída
                    if 'entrada' in df.columns and 'saida' in df.columns and 'data' in df.columns:
                        # Adicionar nome do arquivo para debug
                        df['arquivo_origem'] = main_file.name
                        df['tipo_transacao'] = 'completo'
                        all_data.append(df)
                        files_loaded.append(f"COMPLETO: {main_file.name}")
                        logger.info(f"Planilha principal carregada com {len(df)} linhas")
                    else:
                        logger.warning(f"Planilha {main_file.name} não tem colunas válidas")
                        
                except Exception as e:
                    logger.error(f"Erro ao carregar {main_file.name}: {str(e)}")
            
            # Carregar outras planilhas de entrada se existirem
            for file_path in inflow_dir.glob("*entrada*.xlsx"):
                if file_path.name != "base_de_dados_empresa_longa.xlsx":  # Evitar duplicação
                    try:
                        logger.info(f"Carregando planilha de entrada: {file_path.name}")
                        df = pd.read_excel(file_path)
                        
                        # Verificar se tem colunas de entrada
                        if 'VALOR' in df.columns and 'DATA' in df.columns:
                            # Adicionar nome do arquivo para debug
                            df['arquivo_origem'] = file_path.name
                            df['tipo_transacao'] = 'entrada'
                            all_data.append(df)
                            files_loaded.append(f"ENTRADA: {file_path.name}")
                        else:
                            logger.warning(f"Planilha {file_path.name} não tem colunas de entrada válidas")
                            
                    except Exception as e:
                        logger.error(f"Erro ao carregar {file_path.name}: {str(e)}")
                        continue
        
        if not all_data:
            logger.warning("Nenhuma planilha válida foi carregada")
            return None
        
        # Concatenar todos os dados
        df_combined = pd.concat(all_data, ignore_index=True)
        logger.info(f"Carregadas {len(files_loaded)} planilhas: {files_loaded}")
        logger.info(f"Total de linhas: {len(df_combined)}")
        
        # Processar os dados usando a função existente
        df_processed = processar_dados(df_combined, filename="planilhas_combined")
        
        return df_processed
        
    except Exception as e:
        logger.error(f"Erro ao carregar dados das planilhas: {str(e)}")
        traceback.print_exc()
        return None

def load_key_business_events_from_excel():
    """
    Carrega dados reais das planilhas de saída e entrada para identificar os principais fornecedores e clientes.
    Retorna dados no formato esperado pelo frontend.
    """
    try:
        import pandas as pd
        from pathlib import Path
        
        # Caminho para as planilhas (usando caminho absoluto)
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = Path(current_dir).parent.parent / "data"
        outflow_dir = data_dir / "dados_de_saida"
        inflow_file = data_dir / "Planilha_Entradas.xls"
        
        result_outflows = []
        result_inflows = []
        
        # === CARREGAR DADOS DE SAÍDA (FORNECEDORES) ===
        if outflow_dir.exists():
            logger.info(f"Carregando planilhas de saída de: {outflow_dir}")
            all_outflows = []
            files_loaded = []
            
            # Carregar todas as planilhas de saída
            for file_path in outflow_dir.glob("*.xlsx"):
                try:
                    logger.info(f"Carregando planilha de saída: {file_path.name}")
                    df = pd.read_excel(file_path)
                    
                    # Verificar se tem as colunas necessárias (SAIDA, VALOR, DATA)
                    required_cols = ['SAIDA', 'VALOR', 'DATA']
                    missing_cols = [col for col in required_cols if col not in df.columns]
                    
                    if missing_cols:
                        logger.warning(f"Planilha {file_path.name} não tem colunas: {missing_cols}")
                        continue
                    
                    # Filtrar linhas válidas (remover NaN, valores vazios)
                    df = df.dropna(subset=['SAIDA', 'VALOR'])
                    df = df[df['SAIDA'].astype(str).str.strip() != '']
                    df = df[df['SAIDA'].astype(str).str.lower() != 'nan']
                    df = df[df['VALOR'] > 0]
                    
                    if len(df) > 0:
                        all_outflows.append(df)
                        files_loaded.append(file_path.name)
                        logger.info(f"Planilha {file_path.name} carregada com {len(df)} linhas válidas")
                    
                except Exception as e:
                    logger.error(f"Erro ao carregar {file_path.name}: {str(e)}")
                    continue
            
            if all_outflows:
                # Concatenar todos os dados de saída
                df_combined = pd.concat(all_outflows, ignore_index=True)
                logger.info(f"Carregadas {len(files_loaded)} planilhas de saída: {files_loaded}")
                logger.info(f"Total de linhas de saída: {len(df_combined)}")
                
                # Normalizar nomes dos fornecedores (maiúsculas/minúsculas)
                df_combined['SAIDA_NORMALIZED'] = df_combined['SAIDA'].astype(str).str.strip().str.title()
                
                # Agrupar por fornecedor normalizado e calcular estatísticas
                grouped = df_combined.groupby('SAIDA_NORMALIZED').agg({
                    'VALOR': ['sum', 'count', 'mean']
                }).reset_index()
                
                # Renomear colunas para facilitar o acesso
                grouped.columns = ['name', 'total_amount', 'frequency', 'avg_amount']
                
                # Filtrar fornecedores com nomes válidos (não genéricos)
                grouped = grouped[~grouped['name'].astype(str).str.contains('MATERIAIS DIVERSOS', case=False, na=False)]
                grouped = grouped[~grouped['name'].astype(str).str.contains('nan', case=False, na=False)]
                grouped = grouped[grouped['name'].astype(str).str.strip() != '']
                
                # Ordenar por total_amount (decrescente) e pegar top 5
                key_outflows = grouped.sort_values('total_amount', ascending=False).head(5)
                
                # Converter para formato esperado pelo frontend
                for _, row in key_outflows.iterrows():
                    result_outflows.append({
                        "name": str(row['name']).strip(),
                        "total_amount": float(row['total_amount']),
                        "frequency": int(row['frequency']),
                        "avg_amount": float(row['avg_amount'])
                    })
                
                logger.info(f"Identificados {len(result_outflows)} principais fornecedores")
                for outflow in result_outflows:
                    logger.info(f"  - {outflow['name']}: R$ {outflow['total_amount']:.2f} ({outflow['frequency']} transações)")
        
        # === CARREGAR DADOS DE ENTRADA (PRODUTOS) ===
        if inflow_file.exists():
            logger.info(f"Carregando planilha de entrada: {inflow_file.name}")
            try:
                df_inflow = pd.read_excel(inflow_file)
                
                # Verificar se tem as colunas necessárias para análise de produtos
                required_cols = ['Data', 'Descrição', 'Valor Pago']
                missing_cols = [col for col in required_cols if col not in df_inflow.columns]
                
                if missing_cols:
                    logger.warning(f"Planilha de entrada não tem colunas: {missing_cols}")
                else:
                    # Filtrar apenas vendas válidas (não canceladas)
                    df_inflow = df_inflow[df_inflow['Cancelado'] != 'Sim']
                    df_inflow = df_inflow.dropna(subset=['Descrição', 'Valor Pago'])
                    df_inflow = df_inflow[df_inflow['Valor Pago'] > 0]
                    
                    if len(df_inflow) > 0:
                        logger.info(f"Planilha de entrada carregada com {len(df_inflow)} vendas válidas")
                        
                        # Processar produtos das descrições usando a lógica do business_event_analyzer
                        from core.business_event_analyzer import _split_inflow_description_with_quantities
                        from core.data_processing import processar_descricao_multiplos_produtos
                        
                        # Construir mapa de preços unitários conhecidos
                        precos_unitarios_por_produto = {}
                        for _, row in df_inflow.iterrows():
                            valor_total = float(row.get('Valor Pago', 0) or 0)
                            desc = row.get('Descrição', '')
                            itens = _split_inflow_description_with_quantities(desc)
                            
                            # Se é um item único, calcula o preço unitário
                            if len(itens) == 1:
                                qtd, produto = itens[0]
                                if qtd > 0 and produto:
                                    preco_unitario = valor_total / qtd
                                    if produto not in precos_unitarios_por_produto:
                                        precos_unitarios_por_produto[produto] = []
                                    precos_unitarios_por_produto[produto].append(preco_unitario)
                        
                        # Calcula preços médios para produtos com múltiplas transações
                        for produto in precos_unitarios_por_produto:
                            if len(precos_unitarios_por_produto[produto]) > 1:
                                precos_unitarios_por_produto[produto] = [sum(precos_unitarios_por_produto[produto]) / len(precos_unitarios_por_produto[produto])]
                            else:
                                precos_unitarios_por_produto[produto] = precos_unitarios_por_produto[produto]
                        
                        # Converte para formato esperado pela função processar_descricao_multiplos_produtos
                        precos_map = {produto: precos[0] for produto, precos in precos_unitarios_por_produto.items()}
                        
                        # Processar todas as transações para extrair produtos individuais
                        expanded_rows = []
                        for _, row in df_inflow.iterrows():
                            valor_total = float(row.get('Valor Pago', 0) or 0)
                            desc = row.get('Descrição', '')
                            
                            # Usa a função para processar descrições com múltiplos produtos
                            itens_processados = processar_descricao_multiplos_produtos(desc, valor_total, precos_map)
                            
                            for qtd, produto, valor_item in itens_processados:
                                expanded_rows.append({
                                    'produto': produto,
                                    'valor': valor_item,
                                    'quantidade': qtd
                                })
                        
                        if expanded_rows:
                            # Criar DataFrame expandido e agrupar por produto
                            df_expanded = pd.DataFrame(expanded_rows)
                            
                            # Agrupar por produto e calcular estatísticas
                            grouped_products = df_expanded.groupby('produto').agg({
                                'valor': ['sum', 'count'],
                                'quantidade': 'sum'
                            }).reset_index()
                            
                            # Renomear colunas
                            grouped_products.columns = ['name', 'total_amount', 'frequency', 'total_quantity']
                            
                            # Filtrar produtos com nomes válidos
                            grouped_products = grouped_products[grouped_products['name'].astype(str).str.strip() != '']
                            grouped_products = grouped_products[~grouped_products['name'].astype(str).str.contains('nan', case=False, na=False)]
                            
                            # Ordenar por total_amount (decrescente) e pegar top 5
                            key_inflows = grouped_products.sort_values('total_amount', ascending=False).head(5)
                            
                            # Converter para formato esperado pelo frontend
                            for _, row in key_inflows.iterrows():
                                result_inflows.append({
                                    "name": str(row['name']).strip(),
                                    "total_amount": float(row['total_amount']),
                                    "frequency": int(row['frequency']),
                                    "avg_amount": float(row['total_amount'] / row['frequency']) if row['frequency'] > 0 else 0.0
                                })
                            
                            logger.info(f"Identificados {len(result_inflows)} principais produtos")
                            for inflow in result_inflows:
                                logger.info(f"  - {inflow['name']}: R$ {inflow['total_amount']:.2f} ({inflow['frequency']} transações)")
                        else:
                            logger.warning("Nenhum produto válido encontrado nas descrições")
                
            except Exception as e:
                logger.error(f"Erro ao carregar planilha de entrada: {str(e)}")
        
        # Retornar resultado combinado
        if result_outflows or result_inflows:
            return {
                "key_outflows": result_outflows,
                "key_inflows": result_inflows
            }
        else:
            logger.warning("Nenhum dado válido foi carregado")
            return None
        
    except Exception as e:
        logger.error(f"Erro ao carregar eventos de negócio das planilhas: {str(e)}")
        traceback.print_exc()
        return None

# --- Endpoints da API ---

@router.get("/key-business-events")
async def get_key_business_events(user: dict = Depends(get_current_user)):
    """
    Endpoint: Retorna a lista de principais produtos (receitas) e custos para
    popular a interface de simulação de eventos.
    """
    try:
        # Primeiro, tenta carregar dados reais das planilhas de saída
        logger.info("=== INICIANDO CARREGAMENTO DE DADOS REAIS ===")
        logger.info("Tentando carregar dados reais das planilhas de saída...")
        excel_events = load_key_business_events_from_excel()
        
        if excel_events is not None:
            logger.info("=== DADOS REAIS CARREGADOS COM SUCESSO! ===")
            logger.info(f"Retornando {len(excel_events.get('key_outflows', []))} fornecedores")
            return excel_events
        else:
            logger.warning("=== FALHA AO CARREGAR DADOS REAIS ===")
        
        # Se não conseguiu carregar das planilhas, tenta dados processados do usuário
        user_df = _user_df(user)
        if user_df is not None and not user_df.empty:
            logger.info("Usando dados processados da sessão do usuário")
            events = identify_key_business_events(user_df, top_n=5)
            return events
        else:
            logger.warning("Nenhum dado real disponível, usando dados mock")
            mock_historical_df = create_mock_historical_data(180)
            events = identify_key_business_events(mock_historical_df, top_n=5)
            return events
        
    except Exception as e:
        logger.error(f"Erro ao analisar eventos de negócio: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao analisar eventos de negócio: {str(e)}")

@router.post("/scenario-simulation", response_model=SimulationResponse)
async def simulate_scenario(request: SimulationRequest, user: dict = Depends(get_current_user)):
    """
    Endpoint PRINCIPAL: Executa uma simulação com base no tipo especificado
    ('macroeconomic' ou 'event').
    """
    try:
        logger.info(f"🔄 Recebida requisição de simulação: {request.simulation_type}")
        
        # Validação inicial do tipo de simulação
        if request.simulation_type not in ['macroeconomic', 'event', 'loan_impact']:
            raise HTTPException(
                status_code=400, 
                detail=f"Tipo de simulação inválido: '{request.simulation_type}'. Use 'macroeconomic', 'event' ou 'loan_impact'."
            )

        # Para simulação macroeconômica, usa dados mock
        if request.simulation_type == "macroeconomic":
            logger.info(f"🔄 Iniciando simulação MACROECONÔMICA: {request.scenario_type}")
            
            # Cria dados base para comparação
            df_original = create_mock_forecast_data(12)
            
            # Converte regras de sazonalidade para dict se existirem
            seasonality_dict = []
            if request.seasonality_rules:
                seasonality_dict = [rule.dict() for rule in request.seasonality_rules]
            
            # Executa a simulação
            df_simulated = run_simulation(
                forecast_df=df_original.copy(),
                scenario_type=request.scenario_type,
                seasonality_rules=seasonality_dict
            )
            scenario_name = request.scenario_type

        # Para simulação de eventos, precisa dos dados históricos
        elif request.simulation_type == "event":
            logger.info("🔄 Iniciando simulação de EVENTOS DE NEGÓCIO")
            
            # Verifica se há dados históricos, se não houver, cria dados mock
            historical_df = _historical_df(user)
                
            # Valida os dados históricos
            validate_historical_data_for_events(historical_df)
            
            # Converte modificadores para dict
            inflow_mods = [mod.dict() for mod in request.inflow_modifiers or []]
            outflow_mods = [mod.dict() for mod in request.outflow_modifiers or []]
            
            # Executa a simulação de eventos
            df_simulated_monthly = run_event_simulation(
                historical_df=historical_df,
                inflow_modifiers=inflow_mods,
                outflow_modifiers=outflow_mods
            )
            
            # Debug: Vamos ver que colunas estão disponíveis
            logger.info(f"Colunas disponíveis no resultado da simulação: {list(df_simulated_monthly.columns)}")
            
            # Mapeia as colunas corretamente baseado no que está disponível
            if 'entrada' in df_simulated_monthly.columns:
                receita_col = 'entrada'
                custo_col = 'saida'
                fluxo_col = 'fluxo_diario'
            elif 'receita_total' in df_simulated_monthly.columns:
                receita_col = 'receita_total'
                custo_col = 'custo_total'
                fluxo_col = 'fluxo_de_caixa'
            else:
                # Se não encontra as colunas esperadas, cria valores padrão
                logger.warning("⚠️ Colunas esperadas não encontradas, criando estrutura padrão")
                df_simulated_monthly['entrada'] = 0
                df_simulated_monthly['saida'] = 0
                df_simulated_monthly['fluxo_diario'] = 0
                receita_col = 'entrada'
                custo_col = 'saida'
                fluxo_col = 'fluxo_diario'
            
            # Adapta o resultado para o formato de resposta padrão
            df_simulated = pd.DataFrame({
                "mes": df_simulated_monthly['mes'] if 'mes' in df_simulated_monthly.columns else [f"Mês {i+1}" for i in range(len(df_simulated_monthly))],
                "receita_total": df_simulated_monthly[receita_col],
                "custo_total": df_simulated_monthly[custo_col],
                "fluxo_de_caixa": df_simulated_monthly[fluxo_col]
            })
            
            # Para eventos, usa dados históricos como baseline
            df_original = create_mock_forecast_data(len(df_simulated))
            scenario_name = "event-based"

        elif request.simulation_type == "loan_impact":
            print("🚀 Executando simulação de Impacto de Empréstimo...")
            if not hasattr(request, 'loan_params') or request.loan_params is None:
                raise HTTPException(status_code=400, detail="Parâmetros do empréstimo não fornecidos.")

            historical_df = _historical_df(user)

            df_simulated_monthly = run_loan_simulation(
                historical_df=historical_df,
                amount=request.loan_params.amount,
                interest_rate_monthly=request.loan_params.interest_rate_monthly,
                term_months=request.loan_params.term_months
            )

            # Adaptar para formato padrão
            df_simulated = pd.DataFrame({
                "mes": df_simulated_monthly['mes'] if 'mes' in df_simulated_monthly.columns else [f"Mês {i+1}" for i in range(len(df_simulated_monthly))],
                "receita_total": df_simulated_monthly.get('entrada', pd.Series([0]*len(df_simulated_monthly))),
                "custo_total": df_simulated_monthly.get('saida', pd.Series([0]*len(df_simulated_monthly))),
                "fluxo_de_caixa": df_simulated_monthly.get('fluxo_diario', pd.Series([0]*len(df_simulated_monthly)))
            })

            # baseline mock do mesmo tamanho
            df_original = create_mock_forecast_data(len(df_simulated))
            scenario_name = "loan-impact"

        # Calcula os resumos e detalhes para a resposta
        logger.info("✅ Simulação executada com sucesso. Calculando resumos...")
        
        original_summary = calculate_dataframe_summary(df_original)
        simulated_summary = calculate_dataframe_summary(df_simulated)
        monthly_details = convert_dataframe_to_monthly_details(df_simulated)

        # Construir objeto 'scenarios' (p25, p50, p75) com base em fluxo_de_caixa
        try:
            serie_fluxo = pd.to_numeric(df_simulated.get('fluxo_de_caixa', pd.Series(dtype=float)), errors='coerce').fillna(0)
            p25 = float(np.percentile(serie_fluxo, 25)) if len(serie_fluxo) > 0 else 0.0
            p50 = float(np.percentile(serie_fluxo, 50)) if len(serie_fluxo) > 0 else 0.0
            p75 = float(np.percentile(serie_fluxo, 75)) if len(serie_fluxo) > 0 else 0.0
            scenarios_obj = {
                "pessimista": {"nome": "Cenário Pessimista", "percentil": 25, "valor": p25},
                "mais_provavel": {"nome": "Cenário Mais Provável", "percentil": 50, "valor": p50},
                "otimista": {"nome": "Cenário Otimista", "percentil": 75, "valor": p75},
            }
        except Exception:
            scenarios_obj = None

        response = SimulationResponse(
            scenario_type=scenario_name,
            original_summary=original_summary,
            simulated_summary=simulated_summary,
            monthly_details=monthly_details,
            results_summary=simulated_summary,
            scenarios=scenarios_obj
        )
        
        logger.info(f"✅ Simulação {request.simulation_type} concluída com sucesso")
        return response
        
    except HTTPException as he:
        # Re-raise HTTPException para manter o status code correto
        logger.error(f"❌ HTTPException: {he.detail}")
        raise he
        
    except ValueError as ve:
        logger.error(f"❌ Erro de validação: {str(ve)}")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Erro de validação: {str(ve)}")
        
    except Exception as e:
        logger.error(f"❌ Erro interno na simulação: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro interno ao executar simulação: {str(e)}")

@router.get("/data-availability")
async def check_data_availability(user: dict = Depends(get_current_user)):
    """
    Endpoint para verificar se há dados históricos carregados.
    """
    try:
        df = _user_df(user)
        has_real_data = df is not None and not df.empty
        
        if has_real_data:
            data_info = {
                "has_real_data": True,
                "data_source": "uploaded_file",
                "shape": df.shape,
                "columns": list(df.columns),
                "date_range": {
                    "start": str(df['data'].min()) if 'data' in df.columns else None,
                    "end": str(df['data'].max()) if 'data' in df.columns else None
                }
            }
        else:
            data_info = {
                "has_real_data": False,
                "data_source": "mock_data_will_be_used",
                "message": "Nenhum arquivo foi carregado. Dados mock serão usados para demonstração."
            }
        
        return data_info
        
    except Exception as e:
        logger.error(f"❌ Erro ao verificar disponibilidade dos dados: {str(e)}")
        return {
            "has_real_data": False,
            "error": str(e)
        }

@router.get("/status")
async def get_simulation_status(user: dict = Depends(get_current_user)):
    """Endpoint para verificar o status do módulo de simulação."""
    try:
        df = _user_df(user)
        has_data = df is not None and not df.empty
        
        status_info = {
            "module": "simulations",
            "status": "active",
            "has_data": has_data,
            "available_scenarios": ["pessimista", "mais_provavel", "otimista"],
            "features": ["macroeconomic_simulation", "event_simulation"]
        }
        
        if has_data:
            status_info["data_shape"] = df.shape
            status_info["data_columns"] = list(df.columns)
        
        return status_info
        
    except Exception as e:
        logger.error(f"❌ Erro ao verificar status: {str(e)}")
        return {
            "module": "simulations",
            "status": "error",
            "error": str(e),
            "has_data": False
        }

class MonteCarloRequest(BaseModel):
    """Modelo de requisição para simulação Monte Carlo."""
    variacao_entrada: float = 0.1
    variacao_saida: float = 0.1
    dias_simulacao: int = 30
    num_simulacoes: int = 1000
    saldo_inicial_simulacao: Optional[float] = None

@router.post("/scenarios")
async def execute_monte_carlo_simulation(
    request: MonteCarloRequest,
    user: dict = Depends(get_current_user),
):
    """
    Endpoint para executar simulação Monte Carlo com 3 cenários (pessimista, mais provável, otimista).
    Retorna os percentis 25, 50 e 75 conforme solicitado.
    """
    try:
        from core.mock import ScenarioSimulatorMock
        
        df = _user_df(user)
        if df is None or df.empty:
            logger.warning("Nenhum dado histórico, usando valores padrão para simulação")
            stats = {
                'entrada_media': 1000,
                'entrada_std': 200,
                'saida_media': 800,
                'saida_std': 150,
                'saldo_atual': 5000,
                'periodo_dias': 30
            }
        else:
            stats = ScenarioSimulatorMock.calcular_estatisticas_historicas(df)
        
        # Gera parâmetros da simulação
        params = ScenarioSimulatorMock.gerar_parametros_simulacao(
            stats=stats,
            variacao_entrada=request.variacao_entrada,
            variacao_saida=request.variacao_saida,
            dias_simulacao=request.dias_simulacao,
            num_simulacoes=request.num_simulacoes,
            saldo_inicial=request.saldo_inicial_simulacao
        )
        
        # Executa a simulação Monte Carlo
        df_resultados, _ = ScenarioSimulatorMock.executar_simulacao_monte_carlo(params)
        
        if df_resultados.empty:
            raise HTTPException(status_code=500, detail="Simulação não gerou resultados")
        
        # Analisa probabilidades
        analise = ScenarioSimulatorMock.analisar_probabilidades(df_resultados)
        
        # Retorna resultado com 3 cenários (percentis 25, 50, 75)
        p25 = analise.get("percentil_25", 0)
        p50 = analise.get("percentil_50", 0)
        p75 = analise.get("percentil_75", 0)
        prob_neg = analise.get("prob_saldo_negativo", 0)
        prob_neg_real = analise.get("prob_saldo_negativo_real", prob_neg)
        
        # Log para debug
        logger.info(f"Resultados da análise: P25={p25:.2f}, P50={p50:.2f}, P75={p75:.2f}, Prob_Neg={prob_neg:.4f} ({prob_neg*100:.1f}%), Prob_Real={prob_neg_real:.4f}")
        
        if p75 < 0:
            risk_level = "critico"
            risk_message = "Mesmo o cenário otimista (P75) é negativo"
        elif p50 < 0 or prob_neg >= 0.40:
            risk_level = "alto"
            risk_message = "Mediana negativa ou probabilidade >= 40%"
        elif p25 < 0 or prob_neg >= 0.15:
            risk_level = "medio"
            risk_message = "P25 negativo ou probabilidade >= 15%"
        else:
            risk_level = "baixo"
            risk_message = "Probabilidade baixa de saldo negativo"

        return {
            "results_summary": {
                "prob_saldo_negativo_final": prob_neg,
                "prob_saldo_negativo_qualquer_momento": prob_neg,
                "valor_minimo_esperado": p25,  # Cenário pessimista (25%)
                "valor_mediano_esperado": p50,  # Cenário mais provável (50%)
                "valor_maximo_esperado": p75,  # Cenário otimista (75%)
                "saldo_medio": analise.get("saldo_medio", 0),
                "saldo_std": analise.get("saldo_std", 0),
                "num_simulacoes": analise.get("num_simulacoes", 0),
                "risk_level": risk_level,
                "risk_message": risk_message
            },
            "scenarios": {
                "pessimista": {
                    "nome": "Cenário Pessimista",
                    "percentil": 25,
                    "valor": p25,
                    "descricao": "Apenas 25% dos casos serão piores que este cenário"
                },
                "mais_provavel": {
                    "nome": "Cenário Mais Provável",
                    "percentil": 50,
                    "valor": p50,
                    "descricao": "Valor mediano - 50% dos casos estarão acima ou abaixo"
                },
                "otimista": {
                    "nome": "Cenário Otimista",
                    "percentil": 75,
                    "valor": p75,
                    "descricao": "Apenas 25% dos casos serão melhores que este cenário"
                }
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Erro ao executar simulação Monte Carlo: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao executar simulação: {str(e)}")