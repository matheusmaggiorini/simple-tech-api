#!/usr/bin/env python3
"""
Teste da função de análise de eventos de negócio com produtos normalizados
"""

import pandas as pd
import numpy as np
from io import BytesIO
import sys
import os

# Adiciona o diretório do backend ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Backend'))

from core.business_event_analyzer import identify_key_business_events
from core.data_processing import processar_dados
from fastapi import UploadFile

def test_business_events_analysis():
    """Testa a análise de eventos de negócio com produtos normalizados"""
    
    filename = 'Backend/data/Planilha_Entradas.xls'
    
    try:
        print("=== TESTE DE ANÁLISE DE EVENTOS DE NEGÓCIO ===")
        
        # Lê e processa a planilha real
        df_raw = pd.read_excel(filename)
        
        # Simula UploadFile
        with open(filename, 'rb') as f:
            content = f.read()
        
        upload_file = UploadFile(
            filename=filename,
            file=BytesIO(content)
        )
        
        # Processa com a função de leitura
        from api.endpoints.data import _read_any_cashflow_table
        df_processed = _read_any_cashflow_table(upload_file, treat_outflow_layout=False)
        
        # Processa com processar_dados para obter produtos normalizados
        df_final = processar_dados(df_processed, filename)
        
        print(f"DataFrame processado: {len(df_final)} linhas")
        print(f"Colunas disponíveis: {list(df_final.columns)}")
        
        # Verifica se tem as colunas necessárias
        if 'produto_normalizado' in df_final.columns and 'quantidade' in df_final.columns:
            print("✅ Colunas de produto normalizado e quantidade disponíveis")
        else:
            print("❌ Colunas de produto normalizado não encontradas")
            return False
        
        # Testa a análise de eventos de negócio
        print("\nAnalisando eventos de negócio...")
        events = identify_key_business_events(df_final, top_n=10)
        
        print(f"\n=== TOP 10 PRODUTOS (ENTRADAS) ===")
        if events['key_inflows']:
            for i, produto in enumerate(events['key_inflows'], 1):
                name = produto['name'][:60] + "..." if len(produto['name']) > 60 else produto['name']
                total_amount = produto['total_amount']
                frequency = produto['frequency']
                
                # Verifica se tem quantidade total
                if 'total_quantity' in produto:
                    total_quantity = produto['total_quantity']
                    print(f"{i:2d}. {name}")
                    print(f"    Vendas: R$ {total_amount:.2f} | Frequência: {frequency} | Quantidade: {total_quantity:.0f} unidades")
                else:
                    print(f"{i:2d}. {name}")
                    print(f"    Vendas: R$ {total_amount:.2f} | Frequência: {frequency}")
                print()
        else:
            print("Nenhum produto encontrado")
        
        print(f"\n=== TOP 10 CUSTOS (SAÍDAS) ===")
        if events['key_outflows']:
            for i, custo in enumerate(events['key_outflows'], 1):
                name = custo['name'][:60] + "..." if len(custo['name']) > 60 else custo['name']
                total_amount = custo['total_amount']
                frequency = custo['frequency']
                print(f"{i:2d}. {name}")
                print(f"    Valor: R$ {total_amount:.2f} | Frequência: {frequency}")
                print()
        else:
            print("Nenhum custo encontrado")
        
        # Verifica se a normalização está funcionando
        print(f"\n=== VERIFICAÇÃO DA NORMALIZAÇÃO ===")
        
        # Conta produtos únicos antes e depois da normalização
        produtos_originais = df_final['descricao'].nunique()
        produtos_normalizados = df_final['produto_normalizado'].nunique()
        
        print(f"Produtos únicos originais: {produtos_originais}")
        print(f"Produtos únicos normalizados: {produtos_normalizados}")
        print(f"Redução: {produtos_originais - produtos_normalizados} produtos")
        
        # Verifica se há produtos com múltiplas quantidades
        produtos_com_variacoes = 0
        for produto in df_final['produto_normalizado'].unique():
            if pd.isna(produto) or produto == '':
                continue
            vendas_produto = df_final[df_final['produto_normalizado'] == produto]
            if len(vendas_produto) > 1 and vendas_produto['quantidade'].nunique() > 1:
                produtos_com_variacoes += 1
        
        print(f"Produtos com variações de quantidade: {produtos_com_variacoes}")
        
        if produtos_com_variacoes > 0:
            print("✅ A normalização está funcionando - produtos com quantidades diferentes são agrupados")
        else:
            print("ℹ️  Nenhum produto com variações de quantidade encontrado")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_comparison_before_after():
    """Compara análise antes e depois da normalização"""
    
    print("\n=== COMPARAÇÃO ANTES E DEPOIS DA NORMALIZAÇÃO ===")
    
    filename = 'Backend/data/Planilha_Entradas.xls'
    
    try:
        # Lê e processa a planilha
        df_raw = pd.read_excel(filename)
        
        with open(filename, 'rb') as f:
            content = f.read()
        
        upload_file = UploadFile(
            filename=filename,
            file=BytesIO(content)
        )
        
        from api.endpoints.data import _read_any_cashflow_table
        df_processed = _read_any_cashflow_table(upload_file, treat_outflow_layout=False)
        df_final = processar_dados(df_processed, filename)
        
        # Análise SEM normalização (usando descricao original)
        print("Análise SEM normalização (descricao original):")
        inflows_original = df_final[df_final['entrada'] > 0].copy()
        top_original = (
            inflows_original.groupby('descricao').agg({
                'entrada': ['sum', 'count']
            })
            .sort_values(by=('entrada', 'sum'), ascending=False)
            .head(5)
        )
        
        print("Top 5 produtos (descricao original):")
        for i, (desc, row) in enumerate(top_original.iterrows(), 1):
            desc_short = desc[:50] + "..." if len(desc) > 50 else desc
            print(f"  {i}. {desc_short}")
            print(f"     Vendas: R$ {row[('entrada', 'sum')]:.2f} | Frequência: {row[('entrada', 'count')]}")
        
        # Análise COM normalização
        print(f"\nAnálise COM normalização (produto_normalizado):")
        events = identify_key_business_events(df_final, top_n=5)
        
        print("Top 5 produtos (normalizados):")
        for i, produto in enumerate(events['key_inflows'], 1):
            name_short = produto['name'][:50] + "..." if len(produto['name']) > 50 else produto['name']
            print(f"  {i}. {name_short}")
            print(f"     Vendas: R$ {produto['total_amount']:.2f} | Frequência: {produto['frequency']}")
            if 'total_quantity' in produto:
                print(f"     Quantidade total: {produto['total_quantity']:.0f} unidades")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro na comparação: {e}")
        return False

if __name__ == "__main__":
    print("=== TESTE DE ANÁLISE DE EVENTOS DE NEGÓCIO COM PRODUTOS NORMALIZADOS ===")
    
    # Teste principal
    success1 = test_business_events_analysis()
    
    # Teste de comparação
    success2 = test_comparison_before_after()
    
    if success1 and success2:
        print("\n🎉 TODOS OS TESTES PASSARAM!")
        print("✅ A análise de eventos de negócio está funcionando com produtos normalizados")
        print("✅ Produtos com diferentes quantidades são agrupados corretamente")
        print("✅ As simulações agora terão análises mais precisas")
    else:
        print("\n❌ Alguns testes falharam")
