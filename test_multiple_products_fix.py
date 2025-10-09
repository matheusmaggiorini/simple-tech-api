#!/usr/bin/env python3
"""
Teste da correção para múltiplos produtos em uma descrição
"""

import pandas as pd
import numpy as np
from io import BytesIO
import sys
import os

# Adiciona o diretório do backend ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Backend'))

from core.data_processing import processar_descricao_multiplos_produtos, processar_dados
from fastapi import UploadFile

def test_multiple_products_processing():
    """Testa o processamento de múltiplos produtos"""
    
    print("=== TESTE DE PROCESSAMENTO DE MÚLTIPLOS PRODUTOS ===")
    
    # Testa a função diretamente
    descricao_teste = "10 X SANLIMP 5LT\n10 X ALCOOL 70% 1L\n10 X DESINFETANTE FLO"
    valor_total = 12956.55
    
    print(f"Descrição teste: {descricao_teste}")
    print(f"Valor total: R$ {valor_total}")
    
    produtos_processados = processar_descricao_multiplos_produtos(descricao_teste, valor_total)
    
    print(f"\nProdutos processados:")
    for i, (quantidade, produto, valor) in enumerate(produtos_processados, 1):
        print(f"  {i}. {quantidade} x {produto}")
        print(f"     Valor: R$ {valor:.2f}")
    
    # Verifica se a soma dos valores é igual ao valor total
    soma_valores = sum(valor for _, _, valor in produtos_processados)
    print(f"\nSoma dos valores: R$ {soma_valores:.2f}")
    print(f"Valor total original: R$ {valor_total:.2f}")
    print(f"Diferença: R$ {abs(soma_valores - valor_total):.2f}")
    
    return abs(soma_valores - valor_total) < 0.01

def test_with_dataframe():
    """Testa com DataFrame simulado"""
    
    print("\n=== TESTE COM DATAFRAME ===")
    
    # Cria DataFrame de teste com múltiplos produtos
    dados_teste = {
        'data': ['2024-01-01', '2024-01-02'],
        'descricao': [
            '2 X RATICIDA KROMAX',
            '10 X SANLIMP 5LT\n10 X ALCOOL 70% 1L\n10 X DESINFETANTE FLO'
        ],
        'entrada': [50.00, 12956.55],
        'saida': [0, 0]
    }
    
    df = pd.DataFrame(dados_teste)
    df['data'] = pd.to_datetime(df['data'])
    
    print("DataFrame original:")
    print(df[['descricao', 'entrada']])
    
    # Processa com a função
    df_processado = processar_dados(df, 'teste_multiplos.xlsx')
    
    print(f"\nDataFrame processado:")
    print(f"Linhas originais: 2")
    print(f"Linhas processadas: {len(df_processado)}")
    print(f"Colunas: {list(df_processado.columns)}")
    
    print(f"\nProdutos individuais:")
    for i, row in df_processado.iterrows():
        print(f"  {i+1}. {row['quantidade']} x {row['produto_normalizado']}")
        print(f"     Valor: R$ {row['entrada']:.2f}")
        print(f"     Descrição original: {row.get('descricao_original', 'N/A')[:50]}...")
        print()
    
    # Verifica se os valores somam corretamente
    valor_total_original = df['entrada'].sum()
    valor_total_processado = df_processado['entrada'].sum()
    
    print(f"Valor total original: R$ {valor_total_original:.2f}")
    print(f"Valor total processado: R$ {valor_total_processado:.2f}")
    print(f"Diferença: R$ {abs(valor_total_original - valor_total_processado):.2f}")
    
    return abs(valor_total_original - valor_total_processado) < 0.01

def test_real_data_sample():
    """Testa com uma amostra dos dados reais"""
    
    print("\n=== TESTE COM AMOSTRA DOS DADOS REAIS ===")
    
    # Cria DataFrame com o exemplo problemático
    dados_real = {
        'data': ['2024-01-01'],
        'descricao': ['10 X SANLIMP 5LT\n10 X ALCOOL 70% 1L\n10 X DESINFETANTE FLO'],
        'entrada': [12956.55],
        'saida': [0]
    }
    
    df = pd.DataFrame(dados_real)
    df['data'] = pd.to_datetime(df['data'])
    
    print("Dados reais (antes):")
    print(f"  Descrição: {df['descricao'].iloc[0]}")
    print(f"  Valor: R$ {df['entrada'].iloc[0]:.2f}")
    
    # Processa
    df_processado = processar_dados(df, 'teste_real.xlsx')
    
    print(f"\nDados processados:")
    print(f"  Linhas: {len(df_processado)}")
    
    for i, row in df_processado.iterrows():
        print(f"  {i+1}. {row['quantidade']} x {row['produto_normalizado']}")
        print(f"     Valor: R$ {row['entrada']:.2f}")
    
    # Verifica se agora são produtos separados
    produtos_unicos = df_processado['produto_normalizado'].nunique()
    print(f"\nProdutos únicos: {produtos_unicos}")
    
    if produtos_unicos == 3:
        print("✅ SUCESSO: Os 3 produtos foram separados corretamente!")
        return True
    else:
        print(f"❌ FALHA: Esperado 3 produtos únicos, encontrado {produtos_unicos}")
        return False

if __name__ == "__main__":
    print("=== TESTE DE CORREÇÃO PARA MÚLTIPLOS PRODUTOS ===")
    
    # Teste 1: Função direta
    success1 = test_multiple_products_processing()
    
    # Teste 2: Com DataFrame
    success2 = test_with_dataframe()
    
    # Teste 3: Dados reais
    success3 = test_real_data_sample()
    
    if success1 and success2 and success3:
        print("\n🎉 TODOS OS TESTES PASSARAM!")
        print("✅ A correção para múltiplos produtos está funcionando")
        print("✅ Produtos em uma única descrição são separados corretamente")
        print("✅ Os valores são distribuídos proporcionalmente")
    else:
        print("\n❌ Alguns testes falharam")
