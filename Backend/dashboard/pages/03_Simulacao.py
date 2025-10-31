import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go

# Configuração da página
st.set_page_config(
    page_title="Simulação de Cenários - Simple",
    layout="wide"
)

# URL base da API
API_BASE_URL = "http://localhost:8000"

st.title("Simulação de Cenários Monte Carlo")

st.markdown("""
Esta página permite simular diferentes cenários financeiros usando o método Monte Carlo.
Você pode testar o impacto de variações nas entradas e saídas do seu fluxo de caixa.
""")

# Verificar se há dados carregados
def check_data_loaded():
    try:
        response = requests.get(f"{API_BASE_URL}/api/data/view_processed?limit=1", timeout=5)
        return response.status_code == 200
    except:
        return False

if not check_data_loaded():
    st.warning("⚠️ Nenhum dado encontrado. Por favor, carregue seus dados na página de Upload primeiro.")
    st.stop()

st.success("✅ Dados carregados. Você pode executar simulações!")

# Parâmetros da simulação
st.subheader("⚙️ Configurações da Simulação")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Parâmetros Temporais**")
    
    dias_simulacao = st.number_input(
        "Dias para Simular no Futuro:",
        min_value=1,
        max_value=365,
        value=30,
        help="Quantos dias à frente simular"
    )
    
    num_simulacoes = st.number_input(
        "Número de Simulações:",
        min_value=100,
        max_value=10000,
        value=1000,
        step=100,
        help="Mais simulações = maior precision, mas demora mais"
    )

with col2:
    st.markdown("**Variações Percentuais Esperadas**")
    
    variacao_entrada = st.slider(
        "Variação na Média de Entradas (%):",
        min_value=0.0,
        max_value=100.0,
        value=10.0,
        step=1.0,
        help="Quanto as entradas podem variar"
    ) / 100
    
    variacao_saida = st.slider(
        "Variação na Média de Saídas (%):",
        min_value=0.0,
        max_value=100.0,
        value=10.0,
        step=1.0,
        help="Quanto as saídas podem variar"
    ) / 100

# Saldo inicial personalizado (opcional)
use_custom_balance = st.checkbox("Usar saldo inicial personalizado para simulação")
saldo_inicial_simulacao = None

if use_custom_balance:
    saldo_inicial_simulacao = st.number_input(
        "Saldo Inicial para Simulação (R$):",
        value=0.0,
        help="Deixe em branco para usar o último saldo dos dados"
    )

# Botão para executar simulação
if st.button("Executar Simulação de Cenários", type="primary"):
    with st.spinner(f"Executando {num_simulacoes} simulações para {dias_simulacao} dias..."):
        try:
            # Preparar payload
            payload = {
                "variacao_entrada": variacao_entrada,
                "variacao_saida": variacao_saida,
                "dias_simulacao": dias_simulacao,
                "num_simulacoes": num_simulacoes
            }
            
            if use_custom_balance and saldo_inicial_simulacao is not None:
                payload["saldo_inicial_simulacao"] = saldo_inicial_simulacao
            
            # Fazer requisição para API
            response = requests.post(
                f"{API_BASE_URL}/api/simulations/scenarios",
                json=payload,
                timeout=120  # Aumentar timeout para simulações grandes
            )
            
            if response.status_code == 200:
                result = response.json()
                summary = result.get("results_summary", {})
                
                if summary:
                    # Métricas principais
                    st.subheader("📊 Resultados da Simulação")

                    # Determinar nível de risco com base em P25/P50/P75 e probabilidade
                    valor_pessimista = summary.get("valor_minimo_esperado", 0)
                    valor_provavel = summary.get("valor_mediano_esperado", 0)
                    valor_otimista = summary.get("valor_maximo_esperado", 0)
                    prob_negativo = summary.get("prob_saldo_negativo_final", 0) * 100

                    if valor_otimista < 0:
                        nivel_texto = "Risco Crítico"
                    elif valor_provavel < 0 or prob_negativo >= 40:
                        nivel_texto = "Risco Alto"
                    elif valor_pessimista < 0 or prob_negativo >= 15:
                        nivel_texto = "Risco Médio"
                    else:
                        nivel_texto = "Risco Baixo"

                    col0, col1, col2, col3 = st.columns(4)

                    with col0:
                        st.metric("Nível de Risco", nivel_texto, help="Classificação baseada em P25/P50/P75 e probabilidade")
                    
                    with col1:
                        st.metric(
                            "Cenário Pessimista (25%)",
                            f"R$ {valor_pessimista:,.2f}",
                            help="Apenas 25% dos casos serão piores que este"
                        )
                    
                    with col2:
                        st.metric(
                            "Cenário Mais Provável (50%)",
                            f"R$ {valor_provavel:,.2f}",
                            help="Valor mediano - 50% acima ou abaixo"
                        )
                    
                    with col3:
                        st.metric(
                            "Cenário Otimista (75%)",
                            f"R$ {valor_otimista:,.2f}",
                            help="Apenas 25% dos casos serão melhores que este"
                        )
                    
                    # Métricas de risco em uma segunda linha
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        prob_negativo = summary.get("prob_saldo_negativo_final", 0) * 100
                        st.metric(
                            "Probabilidade Saldo Negativo (Final)",
                            f"{prob_negativo:.1f}%",
                            delta=f"{prob_negativo:.1f}%",
                            delta_color="inverse"
                        )
                    
                    with col2:
                        prob_qualquer = summary.get("prob_saldo_negativo_qualquer_momento", 0) * 100
                        st.metric(
                            "Probabilidade Saldo Negativo (Qualquer Momento)",
                            f"{prob_qualquer:.1f}%",
                            delta=f"{prob_qualquer:.1f}%",
                            delta_color="inverse"
                        )
                    
                    # Gráfico de distribuição (simulado)
                    st.subheader("📈 Análise de Cenários")
                    
                    # Criar dados simulados para visualização
                    import numpy as np
                    
                    # Simular distribuição baseada nos percentis
                    np.random.seed(42)
                    valor_mediano = summary.get("valor_mediano_esperado", 0)
                    std_estimated = (summary.get("valor_maximo_esperado", 0) - summary.get("valor_minimo_esperado", 0)) / 4
                    
                    simulated_values = np.random.normal(valor_mediano, std_estimated, 1000)
                    
                    # Histograma
                    fig = px.histogram(
                        x=simulated_values,
                        nbins=50,
                        title="Distribuição de Possíveis Saldos Finais",
                        labels={"x": "Saldo Final (R$)", "count": "Frequência"}
                    )
                    
                    # Adicionar linhas de referência
                    fig.add_vline(x=0, line_dash="dash", line_color="red", 
                                annotation_text="Saldo Zero")
                    fig.add_vline(x=valor_mediano, line_dash="dash", line_color="blue", 
                                annotation_text="Mediana")
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Análise de risco
                    st.subheader("🚨 Análise de Risco")
                    
                    # Classificação combinando probabilidade e sinais dos percentis
                    risco_msg = None
                    if valor_otimista < 0:
                        risco_msg = ("🔴 **Risco Crítico**: Mesmo o cenário otimista (P75) é negativo", "error")
                    elif valor_provavel < 0 or prob_negativo >= 40:
                        risco_msg = (f"🔴 **Risco Alto**: mediana negativa ou {prob_negativo:.1f}% prob. negativa", "error")
                    elif valor_pessimista < 0 or prob_negativo >= 15:
                        risco_msg = (f"🟡 **Risco Médio**: P25 negativo ou {prob_negativo:.1f}% prob. negativa", "warning")
                    else:
                        risco_msg = (f"🟢 **Risco Baixo**: {prob_negativo:.1f}% de chance de saldo negativo", "success")
                    
                    msg, level = risco_msg
                    if level == "error":
                        st.error(msg)
                    elif level == "warning":
                        st.warning(msg)
                    else:
                        st.success(msg)
                    
                    # Recomendações
                    st.subheader("💡 Recomendações")
                    
                    recomendacoes = []
                    
                    if prob_negativo > 15:
                        recomendacoes.append("⚠️ **Considere reduzir gastos** ou aumentar receitas para diminuir o risco")
                        recomendacoes.append("💰 **Mantenha uma reserva de emergência** equivalente ao cenário pessimista")
                    
                    if prob_qualquer > 25:
                        recomendacoes.append("📅 **Monitore o fluxo diariamente** - há risco de problemas temporários")
                    
                    if valor_pessimista < -1000:
                        recomendacoes.append("🏪 **Considere uma linha de crédito** para cobrir possíveis déficits")
                    
                    if not recomendacoes:
                        recomendacoes.append("✅ **Situação financeira aparenta estar estável** para o período simulado")
                    
                    for rec in recomendacoes:
                        st.markdown(rec)
                    
                    # Detalhes técnicos
                    with st.expander("🔍 Detalhes Técnicos da Simulação"):
                        st.json(summary)
                
                else:
                    st.error("❌ Nenhum resultado foi gerado pela simulação.")
                    
            else:
                error_detail = response.json().get('detail', 'Erro desconhecido')
                st.error(f"❌ Erro ao executar simulação: {error_detail}")
                
        except requests.exceptions.ConnectionError:
            st.error("❌ Erro de conexão com a API. Verifique se a API está rodando.")
        except requests.exceptions.Timeout:
            st.error("❌ Simulação demorou muito. Tente reduzir o número de simulações.")
        except Exception as e:
            st.error(f"❌ Erro inesperado: {str(e)}")

# Informações sobre Monte Carlo
st.subheader("ℹ️ Sobre a Simulação Monte Carlo")
st.markdown("""
- **Método**: Executa milhares de simulações com variações aleatórias
- **Objetivo**: Estimar probabilidades de diferentes cenários futuros
- **Variações**: Baseadas nas suas configurações e dados históricos
- **Resultado**: Distribuição estatística de possíveis resultados
- **Utilidade**: Ajuda na tomada de decisões sob incerteza
""")

# Dicas de uso
with st.expander("💡 Dicas para Usar a Simulação"):
    st.markdown("""
    **Como interpretar os resultados:**
    - **Probabilidade de Saldo Negativo**: Chance de ficar no vermelho
    - **Cenário Pessimista (25%)**: Apenas 25% dos casos serão piores que isso
    - **Cenário Mais Provável (50%)**: Valor mediano - metade dos casos acima, metade abaixo
    - **Cenário Otimista (75%)**: Apenas 25% dos casos serão melhores que isso
    
    **Recomendações de configuração:**
    - **Poucos dados históricos**: Use variações maiores (15-30%)
    - **Dados estáveis**: Use variações menores (5-15%)
    - **Simulações**: 1000-5000 para resultados confiáveis
    - **Período**: 30-90 dias para análises práticas
    """)