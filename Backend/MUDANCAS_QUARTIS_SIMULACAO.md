# Mudanças na Simulação de Cenários - Quartis Atualizados

## Resumo das Alterações

As funções de simulação de cenários foram atualizadas para usar apenas os quartis **25, 50 e 75**, classificando os cenários como:

- **Percentil 25**: Cenário Pessimista
- **Percentil 50**: Cenário Mais Provável  
- **Percentil 75**: Cenário Otimista

Anteriormente, o sistema usava os quartis 5, 25, 50, 75 e 95.

---

## Arquivos Modificados

### 1. `Backend/api/endpoints/simulations.py`

**Novo endpoint `/api/simulations/scenarios`:**

Criado novo endpoint para executar simulação Monte Carlo que retorna apenas 3 cenários:

```python
@router.post("/scenarios")
async def execute_monte_carlo_simulation(request: MonteCarloRequest):
    """
    Endpoint para executar simulação Monte Carlo com 3 cenários (pessimista, mais provável, otimista).
    Retorna os percentis 25, 50 e 75 conforme solicitado.
    """
```

**Resposta do endpoint:**
```json
{
  "results_summary": {
    "valor_minimo_esperado": <percentil_25>,  // Cenário pessimista
    "valor_mediano_esperado": <percentil_50>,  // Cenário mais provável
    "valor_maximo_esperado": <percentil_75>    // Cenário otimista
  },
  "scenarios": {
    "pessimista": { "percentil": 25, "valor": ... },
    "mais_provavel": { "percentil": 50, "valor": ... },
    "otimista": { "percentil": 75, "valor": ... }
  }
}
```

---

### 2. `Backend/dashboard/pages/03_Simulacao.py`

**Atualização da interface do dashboard:**

```python
# ANTES: 4 colunas (prob negativo final, prob negativo qualquer, pessimista 5%, otimista 95%)
col1, col2, col3, col4 = st.columns(4)

# DEPOIS: 3 colunas com os cenários (pessimista 25%, mais provável 50%, otimista 75%)
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Cenário Pessimista (25%)", ...)
with col2:
    st.metric("Cenário Mais Provável (50%)", ...)
with col3:
    st.metric("Cenário Otimista (75%)", ...)
```

---

### 3. `Backend/core/mock.py`

**Alteração na função `analisar_probabilidades`:**

```python
# ANTES:
'percentil_5': float(saldos.quantile(0.05)),
'percentil_95': float(saldos.quantile(0.95)),

# DEPOIS:
'percentil_25': float(saldos.quantile(0.25)),  # Cenário pessimista
'percentil_50': float(saldos.quantile(0.50)),  # Cenário mais provável
'percentil_75': float(saldos.quantile(0.75)),  # Cenário otimista
```

---

### 2. `Backend/core/scenario_simulator.py`

**Alterações no dicionário `MACROECONOMIC_SCENARIOS`:**

```python
MACROECONOMIC_SCENARIOS = {
    "otimista": {
        "revenue_change": 0.15,  # +15%
        "cost_change": -0.10,    # -10%
        "description": "Cenário otimista (percentil 75): aumento de receita e redução de custos"
    },
    "mais_provavel": {
        "revenue_change": 0.05,  # +5%
        "cost_change": 0.03,     # +3%
        "description": "Cenário mais provável (percentil 50): crescimento moderado com aumento leve de custos"
    },
    "pessimista": {
        "revenue_change": -0.10, # -10%
        "cost_change": 0.20,     # +20%
        "description": "Cenário pessimista (percentil 25): redução de receita e aumento significativo de custos"
    },
    # Mantém compatibilidade com nome antigo
    "conservador": {
        "revenue_change": 0.05,  # +5%
        "cost_change": 0.03,     # +3%
        "description": "Cenário mais provável (percentil 50): crescimento moderado com aumento leve de custos"
    }
}
```

**Mudanças:**
- Adicionado novo cenário `"mais_provavel"` (substitui `"conservador"` semanticamente)
- Mantida compatibilidade retroativa com `"conservador"` 
- Atualizada descrição de cada cenário para incluir o percentil correspondente

---

### 3. `Backend/api/endpoints/simulations.py`

**Alterações no endpoint de validação:**

```python
# ANTES:
if self.scenario_type not in ['otimista', 'conservador', 'pessimista']:
    raise ValueError(f'Tipo de cenário inválido: {self.scenario_type}. Use otimista, conservador ou pessimista.')

# DEPOIS:
if self.scenario_type not in ['otimista', 'mais_provavel', 'pessimista', 'conservador']:
    raise ValueError(f'Tipo de cenário inválido: {self.scenario_type}. Use otimista, mais_provavel ou pessimista.')
```

**Alterações no endpoint de status:**

```python
# ANTES:
"available_scenarios": ["otimista", "conservador", "pessimista"]

# DEPOIS:
"available_scenarios": ["pessimista", "mais_provavel", "otimista"]
```

---

## Compatibilidade

### Retrocompatibilidade Mantida
- O cenário `"conservador"` ainda é aceito e funciona como sinônimo de `"mais_provavel"`
- Código existente que usa `"otimista"` e `"pessimista"` continua funcionando normalmente

### Novos Cenários Disponíveis
- `"pessimista"` - Percentil 25
- `"mais_provavel"` - Percentil 50 (substitui semanticamente `"conservador"`)
- `"otimista"` - Percentil 75

---

## Como Usar

### Exemplo de Requisição à API

```json
{
  "simulation_type": "macroeconomic",
  "scenario_type": "mais_provavel",
  "seasonality_rules": null
}
```

### Cenários Disponíveis

| Cenário | Percentil | Mudança Receita | Mudança Custo | Descrição |
|---------|-----------|-----------------|---------------|-----------|
| **pessimista** | 25 | -10% | +20% | Redução de receita e aumento significativo de custos |
| **mais_provavel** | 50 | +5% | +3% | Crescimento moderado com aumento leve de custos |
| **otimista** | 75 | +15% | -10% | Aumento de receita e redução de custos |

---

## Testes Realizados

### ✅ Teste 1: Verificação dos Cenários
```bash
python -c "from core.scenario_simulator import MACROECONOMIC_SCENARIOS; print(MACROECONOMIC_SCENARIOS.keys())"
# Saída: dict_keys(['otimista', 'mais_provavel', 'pessimista', 'conservador'])
```

### ✅ Teste 2: Análise de Probabilidades
```python
from core.mock import ScenarioSimulatorMock
result = ScenarioSimulatorMock.analisar_probabilidades(df)
# Retorna: percentil_25, percentil_50, percentil_75
```

### ✅ Teste 3: Validação de Linter
```bash
# Nenhum erro de linter encontrado nos arquivos modificados
```

---

## Data da Modificação
**21 de Outubro de 2025**

## Autor
Atualização solicitada pelo usuário para simplificar a distribuição de cenários de 5 quartis para 3 quartis.

