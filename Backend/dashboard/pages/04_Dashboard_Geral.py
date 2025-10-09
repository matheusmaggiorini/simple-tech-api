import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import logging

# Configuração da página
st.set_page_config(
    page_title="Dashboard Geral - Simple",
    page_icon="📊",
    layout="wide"
)

# URL base da API
API_BASE_URL = "http://localhost:8000"

st.title("📊 Dashboard Geral - Simple")

# Funções auxiliares com melhor tratamento de erro
@st.cache_data(ttl=60)  # Cache por 1 minuto
def check_data_loaded():
    """Verifica se há dados carregados na API"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/data/view_processed?limit=1", timeout=10)
        if response.status_code == 200:
            data = response.json()
            return len(data) > 0 if isinstance(data, list) else bool(data)
        return False
    except requests.exceptions.ConnectionError:
        st.error("🔌 Não foi possível conectar à API. Verifique se o servidor está rodando.")
        return False
    except requests.exceptions.Timeout:
        st.warning("⏱️ Timeout na conexão com a API.")
        return False
    except Exception as e:
        st.error(f"❌ Erro inesperado ao verificar dados: {str(e)}")
        return False

@st.cache_data(ttl=60)
def get_processed_data(limit=-1):
    """Busca dados processados da API"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/data/view_processed?limit={limit}", timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            if not data:
                st.warning("📊 API conectada, mas nenhum dado foi encontrado.")
                return pd.DataFrame()
            
            # Verificar se é uma lista ou dict
            if isinstance(data, list):
                df = pd.DataFrame(data)
            elif isinstance(data, dict):
                # Se for um dict, pode ter uma chave 'data' ou similar
                if 'data' in data:
                    df = pd.DataFrame(data['data'])
                else:
                    df = pd.DataFrame([data])
            else:
                st.error("❌ Formato de dados inesperado da API")
                return pd.DataFrame()
            
            return df
            
        elif response.status_code == 404:
            st.warning("📂 Endpoint não encontrado. Verifique se a API está atualizada.")
            return pd.DataFrame()
        elif response.status_code == 500:
            st.error("🔧 Erro interno do servidor. Verifique os logs da API.")
            return pd.DataFrame()
        else:
            st.error(f"❌ Erro HTTP {response.status_code}: {response.text}")
            return pd.DataFrame()
            
    except requests.exceptions.ConnectionError:
        st.error("🔌 Não foi possível conectar à API. Verifique se o servidor está rodando na porta 8000.")
        return pd.DataFrame()
    except requests.exceptions.Timeout:
        st.warning("⏱️ Timeout na conexão com a API. Tentando novamente...")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erro inesperado ao buscar dados: {str(e)}")
        return pd.DataFrame()

def validate_dataframe(df):
    """Valida se o DataFrame tem as colunas necessárias"""
    required_columns = ['data', 'entrada', 'saida']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        st.error(f"❌ Colunas obrigatórias ausentes nos dados: {missing_columns}")
        st.info(f"📋 Colunas disponíveis: {list(df.columns)}")
        return False
    
    return True

# Verificar conectividade com a API
with st.spinner("🔍 Verificando conectividade com a API..."):
    api_status = check_data_loaded()

if not api_status:
    st.warning("⚠️ Nenhum dado encontrado ou API indisponível.")
    
    # Mostrar dashboard de exemplo
    st.subheader("📋 Status do Sistema")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        try:
            health_check = requests.get(f"{API_BASE_URL}/health", timeout=5)
            api_online = health_check.status_code == 200
        except:
            api_online = False
        st.metric("Status da API", "🟢 Online" if api_online else "🔴 Offline")
    
    with col2:
        st.metric("Dados Carregados", "❌ Não")
    with col3:
        st.metric("Páginas Disponíveis", "4")
    with col4:
        st.metric("Funcionalidades", "Upload, Previsão, Simulação")
    
    st.info("💡 **Próximos passos:**\n1. Verifique se a API está rodando\n2. Carregue seus dados na página de Upload\n3. Volte para ver as análises")
    
    # Botão para tentar reconectar
    if st.button("🔄 Tentar Reconectar"):
        st.cache_data.clear()
        st.rerun()
    
    st.stop()

# Carregar dados
with st.spinner("📊 Carregando dados..."):
    # Carrega todos os registros processados para garantir totais corretos
    df_data = get_processed_data(limit=-1)

if df_data.empty:
    st.error("❌ Nenhum dado foi retornado da API.")
    
    # Opções de debug
    with st.expander("🔧 Informações de Debug"):
        st.write("**Endpoint testado:**", f"{API_BASE_URL}/api/data/view_processed")
        st.write("**Sugestões:**")
        st.write("1. Verifique se há dados carregados no sistema")
        st.write("2. Confirme se o endpoint da API está correto")
        st.write("3. Verifique os logs da API para erros")
        
    if st.button("🔄 Recarregar Página"):
        st.cache_data.clear()
        st.rerun()
    
    st.stop()

# Validar estrutura dos dados
if not validate_dataframe(df_data):
    st.stop()

st.success(f"✅ Dados carregados com sucesso! ({len(df_data)} registros)")

# Converter e limpar dados
try:
    df_data['data'] = pd.to_datetime(df_data['data'], errors='coerce')
    df_data = df_data.dropna(subset=['data'])  # Remove linhas com datas inválidas
    df_data = df_data.sort_values('data')
    
    # Garantir que valores financeiros são numéricos
    df_data['entrada'] = pd.to_numeric(df_data['entrada'], errors='coerce').fillna(0)
    df_data['saida'] = pd.to_numeric(df_data['saida'], errors='coerce').fillna(0)
    
    # Calcular saldo se não existir
    if 'saldo' not in df_data.columns:
        df_data['saldo'] = (df_data['entrada'] - df_data['saida']).cumsum()
    
except Exception as e:
    st.error(f"❌ Erro ao processar dados: {str(e)}")
    st.stop()

# Botão de atualização
col1, col2 = st.columns([1, 4])
with col1:
    if st.button("🔄 Atualizar Dados"):
        st.cache_data.clear()
        st.rerun()
with col2:
    st.caption(f"Última atualização: {datetime.now().strftime('%H:%M:%S')}")

# Métricas principais
st.subheader("📊 Métricas Principais")

col1, col2, col3, col4 = st.columns(4)

try:
    with col1:
        # Garante soma estritamente da coluna de entradas (coercendo texto -> número)
        total_entrada = pd.to_numeric(df_data['entrada'], errors='coerce').fillna(0).sum()
        st.metric("Total de Entradas", f"R$ {total_entrada:,.2f}")

    with col2:
        total_saida = df_data['saida'].sum()
        st.metric("Total de Saídas", f"R$ {total_saida:,.2f}")

    with col3:
        # Recalcula localmente para evitar divergências vindas do backend
        entradas_num = pd.to_numeric(df_data['entrada'], errors='coerce').fillna(0)
        saidas_num = pd.to_numeric(df_data['saida'], errors='coerce').fillna(0)
        saldo_series = (entradas_num - saidas_num).cumsum()
        saldo_atual = saldo_series.iloc[-1] if len(saldo_series) > 0 else 0
        st.metric("Saldo Atual", f"R$ {saldo_atual:,.2f}")

    with col4:
        # Fluxo líquido: soma diária de (entrada - saída). Fallback para totals.
        if 'fluxo_diario' in df_data.columns:
            fluxo_liquido = pd.to_numeric(df_data['fluxo_diario'], errors='coerce').fillna(0).sum()
        else:
            fluxo_liquido = (pd.to_numeric(df_data['entrada'], errors='coerce').fillna(0) -
                             pd.to_numeric(df_data['saida'], errors='coerce').fillna(0)).sum()
        delta_color = "normal" if fluxo_liquido >= 0 else "inverse"
        st.metric("Fluxo de Caixa Líquido", f"R$ {fluxo_liquido:,.2f}", 
                  delta=f"R$ {fluxo_liquido:,.2f}")

except Exception as e:
    st.error(f"❌ Erro ao calcular métricas: {str(e)}")

# Gráficos principais
try:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📈 Evolução do Saldo")
        if len(df_data) > 0:
            fig_saldo = px.line(df_data, x='data', y='saldo', 
                               title="Evolução do Saldo ao Longo do Tempo")
            fig_saldo.add_hline(y=0, line_dash="dash", line_color="red", 
                               annotation_text="Linha Zero")
            fig_saldo.update_layout(
                xaxis_title="Data",
                yaxis_title="Saldo (R$)"
            )
            st.plotly_chart(fig_saldo, use_container_width=True)
        else:
            st.info("Sem dados suficientes para gráfico de saldo")

    with col2:
        st.subheader("💰 Entradas vs Saídas")
        
        if len(df_data) > 0:
            # Preferir resumo mensal vindo do backend (evita divergências)
            try:
                resp = requests.get(f"{API_BASE_URL}/api/data/monthly_summary", timeout=15)
                if resp.status_code == 200:
                    monthly_json = resp.json()
                    df_monthly = pd.DataFrame(monthly_json)
                    df_monthly['periodo_str'] = df_monthly['ano_mes']
                else:
                    # Fallback local
                    df_data['periodo'] = df_data['data'].dt.to_period('M')
                    df_monthly = df_data.groupby('periodo').agg({
                        'entrada': 'sum',
                        'saida': 'sum'
                    }).reset_index()
                    df_monthly['periodo_str'] = df_monthly['periodo'].astype(str)
            except Exception:
                df_data['periodo'] = df_data['data'].dt.to_period('M')
                df_monthly = df_data.groupby('periodo').agg({
                    'entrada': 'sum',
                    'saida': 'sum'
                }).reset_index()
                df_monthly['periodo_str'] = df_monthly['periodo'].astype(str)
            
            fig_bars = go.Figure()
            fig_bars.add_trace(go.Bar(name='Entradas', x=df_monthly['periodo_str'], 
                                     y=df_monthly['entrada'], marker_color='green'))
            fig_bars.add_trace(go.Bar(name='Saídas', x=df_monthly['periodo_str'], 
                                     y=df_monthly['saida'], marker_color='red'))
            fig_bars.update_layout(
                title="Entradas vs Saídas por Mês", 
                barmode='group',
                xaxis_title="Período",
                yaxis_title="Valor (R$)"
            )
            st.plotly_chart(fig_bars, use_container_width=True)
            with st.expander("Debug: Tabela mensal calculada"):
                st.write(df_monthly[['periodo_str', 'entrada', 'saida']].head(24))
                st.caption("A soma abaixo deve bater com as métricas principais")
                st.write({
                    'soma_entradas_mensal': float(pd.to_numeric(df_monthly['entrada'], errors='coerce').fillna(0).sum()),
                    'soma_saidas_mensal': float(pd.to_numeric(df_monthly['saida'], errors='coerce').fillna(0).sum()),
                    'soma_entradas_raw': float(pd.to_numeric(df_data['entrada'], errors='coerce').fillna(0).sum()),
                    'soma_saidas_raw': float(pd.to_numeric(df_data['saida'], errors='coerce').fillna(0).sum()),
                })
        else:
            st.info("Sem dados suficientes para gráfico mensal")

except Exception as e:
    st.error(f"❌ Erro ao gerar gráficos: {str(e)}")

# Análise temporal
st.subheader("Análise Temporal")

try:
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Período dos Dados**")
        if len(df_data) > 0:
            data_inicio = df_data['data'].min()
            data_fim = df_data['data'].max()
            dias_dados = (data_fim - data_inicio).days
            st.write(f"📅 {data_inicio.strftime('%d/%m/%Y')} até {data_fim.strftime('%d/%m/%Y')}")
            st.write(f"⏱️ {dias_dados} dias de histórico")
        else:
            st.write("📅 Sem dados disponíveis")

    with col2:
        st.markdown("**Médias Diárias**")
        if len(df_data) > 0:
            media_entrada = df_data['entrada'].mean()
            media_saida = df_data['saida'].mean()
            st.write(f"💰 Entrada: R$ {media_entrada:,.2f}")
            st.write(f"💸 Saída: R$ {media_saida:,.2f}")
        else:
            st.write("💰 Sem dados para calcular médias")

    with col3:
        st.markdown("**Variabilidade**")
        if len(df_data) > 1:
            std_entrada = df_data['entrada'].std()
            std_saida = df_data['saida'].std()
            st.write(f"📊 Entrada (σ): R$ {std_entrada:,.2f}")
            st.write(f"📊 Saída (σ): R$ {std_saida:,.2f}")
        else:
            st.write("📊 Dados insuficientes para variabilidade")

except Exception as e:
    st.error(f"❌ Erro na análise temporal: {str(e)}")

# Análise de risco rápida
st.subheader("🚨 Análise de Risco Rápida")

try:
    if len(df_data) > 0:
        # Calcular alguns indicadores de risco
        dias_saldo_negativo = len(df_data[df_data['saldo'] < 0])
        pct_dias_negativos = (dias_saldo_negativo / len(df_data)) * 100

        col1, col2, col3 = st.columns(3)

        with col1:
            if pct_dias_negativos > 20:
                st.error(f"🔴 Alto Risco: {pct_dias_negativos:.1f}% dos dias com saldo negativo")
            elif pct_dias_negativos > 5:
                st.warning(f"🟡 Risco Médio: {pct_dias_negativos:.1f}% dos dias com saldo negativo")
            else:
                st.success(f"🟢 Baixo Risco: {pct_dias_negativos:.1f}% dos dias com saldo negativo")

        with col2:
            # Volatilidade simples baseada no desvio padrão do saldo
            volatilidade = df_data['saldo'].std()
            st.metric("Volatilidade do Saldo", f"R$ {volatilidade:,.2f}")

        with col3:
            # Maior déficit
            menor_saldo = df_data['saldo'].min()
            st.metric("Menor Saldo Registrado", f"R$ {menor_saldo:,.2f}")
    else:
        st.info("Sem dados suficientes para análise de risco")

except Exception as e:
    st.error(f"❌ Erro na análise de risco: {str(e)}")

# Tabela de dados recentes
st.subheader("Transações Recentes")

try:
    if len(df_data) > 0:
        recent_data = df_data.tail(10).copy()

        # Formatar para exibição
        recent_data['data_formatada'] = recent_data['data'].dt.strftime('%d/%m/%Y')
        recent_data['entrada_formatada'] = recent_data['entrada'].apply(lambda x: f"R$ {x:,.2f}")
        recent_data['saida_formatada'] = recent_data['saida'].apply(lambda x: f"R$ {x:,.2f}")
        recent_data['saldo_formatado'] = recent_data['saldo'].apply(lambda x: f"R$ {x:,.2f}")

        # Selecionar colunas para exibição
        display_columns = ['data_formatada', 'entrada_formatada', 'saida_formatada', 'saldo_formatado']
        if 'descricao' in recent_data.columns:
            display_columns.insert(1, 'descricao')

        display_df = recent_data[display_columns].copy()
        
        # Renomear colunas
        column_mapping = {
            'data_formatada': 'Data',
            'descricao': 'Descrição',
            'entrada_formatada': 'Entrada',
            'saida_formatada': 'Saída',
            'saldo_formatado': 'Saldo'
        }
        display_df = display_df.rename(columns=column_mapping)

        st.dataframe(display_df, use_container_width=True)
    else:
        st.info("Nenhuma transação encontrada")

except Exception as e:
    st.error(f"❌ Erro ao exibir transações recentes: {str(e)}")


# Rodapé
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    st.caption("Simple - Dashboard Financeiro")
with col2:
    st.caption(f"📊 {len(df_data)} transações analisadas")
with col3:
    st.caption(f"🕐 Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M')}")