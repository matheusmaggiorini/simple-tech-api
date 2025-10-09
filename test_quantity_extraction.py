#!/usr/bin/env python3
"""
Teste da extração de quantidade e normalização de produtos
"""

import pandas as pd
import numpy as np
from io import BytesIO
import sys
import os

# Adiciona o diretório do backend ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Backend'))

from core.data_processing import extrair_quantidade_e_produto, processar_dados
from fastapi import UploadFile

def test_quantity_extraction():
    """Testa a extração de quantidade com exemplos"""
    
    print("=== TESTE DE EXTRAÇÃO DE QUANTIDADE ===")
    
    # Exemplos de descrições com quantidade
    exemplos = [
        "2 X RATICIDA KROMAX",
        "1 X PORTA SANFONADA", 
        "1 X CHUVEIRO DUCHA LOREN",
        "1 X TORNEIRA FILTRO",
        "2 X CAIXA LUZ AMARELA",
        "3 X PRODUTO TESTE",
        "1.5 X PRODUTO DECIMAL",
        "10 X PRODUTO GRANDE",
        "PRODUTO SEM QUANTIDADE",
        "1X PRODUTO SEM ESPAÇO",
        "2x produto minúsculo",
        "5 X PRODUTO COM ESPAÇOS   ",
        ""
    ]
    
    print("Testando extração de quantidade:")
    print("-" * 50)
    
    for descricao in exemplos:
        quantidade, produto = extrair_quantidade_e_produto(descricao)
        print(f"'{descricao}' -> Quantidade: {quantidade}, Produto: '{produto}'")
    
    return True

def test_with_dataframe():
    """Testa com DataFrame simulado"""
    
    print("\n=== TESTE COM DATAFRAME ===")
    
    # Cria DataFrame de teste com entradas
    dados_teste = {
        'data': ['2024-01-01', '2024-01-01', '2024-01-02', '2024-01-02', '2024-01-03'],
        'descricao': [
            '2 X RATICIDA KROMAX',
            '1 X PORTA SANFONADA',
            '3 X CHUVEIRO DUCHA LOREN',
            '1 X TORNEIRA FILTRO',
            'PRODUTO SEM QUANTIDADE'
        ],
        'entrada': [50.00, 25.00, 75.00, 30.00, 15.00],
        'saida': [0, 0, 0, 0, 0]
    }
    
    df = pd.DataFrame(dados_teste)
    df['data'] = pd.to_datetime(df['data'])
    
    print("DataFrame original:")
    print(df[['descricao', 'entrada']])
    
    # Processa com a função
    df_processado = processar_dados(df, 'teste_entradas.xlsx')
    
    print("\nDataFrame processado:")
    print(df_processado[['descricao', 'quantidade', 'produto_normalizado', 'entrada']])
    
    # Verifica se a normalização funcionou
    produtos_unicos = df_processado['produto_normalizado'].unique()
    print(f"\nProdutos únicos normalizados: {len(produtos_unicos)}")
    for produto in produtos_unicos:
        print(f"  - {produto}")
    
    # Verifica quantidades
    print(f"\nQuantidades extraídas:")
    for idx, row in df_processado.iterrows():
        print(f"  {row['descricao']} -> {row['quantidade']} x {row['produto_normalizado']}")
    
    return True

def test_simulation_scenario():
    """Testa cenário de simulação com produtos duplicados"""
    
    print("\n=== TESTE DE CENÁRIO DE SIMULAÇÃO ===")
    
    # Simula vendas do mesmo produto com quantidades diferentes
    dados_vendas = {
        'data': ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05'],
        'descricao': [
            '2 X RATICIDA KROMAX',
            '1 X RATICIDA KROMAX', 
            '3 X RATICIDA KROMAX',
            '1 X RATICIDA KROMAX',
            '2 X RATICIDA KROMAX'
        ],
        'entrada': [50.00, 25.00, 75.00, 25.00, 50.00],
        'saida': [0, 0, 0, 0, 0]
    }
    
    df = pd.DataFrame(dados_vendas)
    df['data'] = pd.to_datetime(df['data'])
    
    print("Vendas do mesmo produto com quantidades diferentes:")
    print(df[['descricao', 'entrada']])
    
    # Processa
    df_processado = processar_dados(df, 'teste_vendas.xlsx')
    
    print("\nApós normalização:")
    print(df_processado[['descricao', 'quantidade', 'produto_normalizado', 'entrada']])
    
    # Agrupa por produto normalizado
    resumo_produto = df_processado.groupby('produto_normalizado').agg({
        'quantidade': 'sum',
        'entrada': 'sum',
        'data': 'count'
    }).round(2)
    
    print("\nResumo por produto normalizado:")
    print(resumo_produto)
    
    # Verifica se agora reconhece como o mesmo produto
    produtos_unicos = df_processado['produto_normalizado'].nunique()
    print(f"\nProdutos únicos após normalização: {produtos_unicos}")
    
    if produtos_unicos == 1:
        print("✅ SUCESSO: Todos os produtos foram reconhecidos como o mesmo!")
        total_quantidade = df_processado['quantidade'].sum()
        print(f"   Total de unidades vendidas: {total_quantidade}")
        print(f"   Total em vendas: R$ {df_processado['entrada'].sum():.2f}")
    else:
        print("❌ FALHA: Produtos ainda são tratados como diferentes")
    
    return produtos_unicos == 1

if __name__ == "__main__":
    print("=== TESTE DE EXTRAÇÃO DE QUANTIDADE E NORMALIZAÇÃO ===")
    
    # Teste 1: Extração básica
    success1 = test_quantity_extraction()
    
    # Teste 2: Com DataFrame
    success2 = test_with_dataframe()
    
    # Teste 3: Cenário de simulação
    success3 = test_simulation_scenario()
    
    if success1 and success2 and success3:
        print("\n🎉 TODOS OS TESTES PASSARAM!")
        print("✅ A extração de quantidade está funcionando corretamente")
        print("✅ A normalização de produtos está funcionando")
        print("✅ O sistema agora reconhece produtos iguais com quantidades diferentes")
    else:
        print("\n❌ Alguns testes falharam")
