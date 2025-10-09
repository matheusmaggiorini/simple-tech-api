#!/usr/bin/env python3
"""
Teste com a planilha real de entradas
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

def test_real_entradas():
    """Testa com a planilha real de entradas"""
    
    filename = 'Backend/data/Planilha_Entradas.xls'
    
    try:
        print("=== TESTE COM PLANILHA REAL DE ENTRADAS ===")
        
        # Lê a planilha
        df_raw = pd.read_excel(filename)
        print(f"Planilha carregada: {len(df_raw)} linhas, {len(df_raw.columns)} colunas")
        
        # Mostra algumas descrições originais
        print("\nExemplos de descrições originais:")
        for i, desc in enumerate(df_raw['Descrição'].head(5)):
            print(f"  {i+1}. {desc}")
        
        # Testa extração de quantidade em algumas descrições
        print("\nTestando extração de quantidade:")
        print("-" * 60)
        
        for i, desc in enumerate(df_raw['Descrição'].head(10)):
            quantidade, produto = extrair_quantidade_e_produto(desc)
            print(f"{i+1:2d}. '{desc[:50]}...' -> Qtd: {quantidade}, Produto: '{produto[:30]}...'")
        
        # Simula UploadFile para processar
        with open(filename, 'rb') as f:
            content = f.read()
        
        upload_file = UploadFile(
            filename=filename,
            file=BytesIO(content)
        )
        
        # Processa com a função de leitura
        from api.endpoints.data import _read_any_cashflow_table
        df_processed = _read_any_cashflow_table(upload_file, treat_outflow_layout=False)
        
        print(f"\nDataFrame após leitura:")
        print(f"  Linhas: {len(df_processed)}")
        print(f"  Colunas: {list(df_processed.columns)}")
        
        if not df_processed.empty:
            # Processa com processar_dados
            df_final = processar_dados(df_processed, filename)
            
            print(f"\nDataFrame após processamento completo:")
            print(f"  Linhas: {len(df_final)}")
            print(f"  Colunas: {list(df_final.columns)}")
            
            # Verifica se tem as novas colunas
            if 'quantidade' in df_final.columns and 'produto_normalizado' in df_final.columns:
                print(f"\n✅ Colunas de quantidade e produto normalizado criadas!")
                
                # Mostra exemplos de normalização
                print(f"\nExemplos de normalização:")
                print("-" * 80)
                for i, row in df_final.head(10).iterrows():
                    print(f"{i+1:2d}. Original: '{row['descricao'][:40]}...'")
                    print(f"    Normalizado: {row['quantidade']} x '{row['produto_normalizado'][:40]}...'")
                    print()
                
                # Análise de produtos únicos
                produtos_originais = df_final['descricao'].nunique()
                produtos_normalizados = df_final['produto_normalizado'].nunique()
                
                print(f"Análise de produtos:")
                print(f"  Produtos únicos originais: {produtos_originais}")
                print(f"  Produtos únicos normalizados: {produtos_normalizados}")
                print(f"  Redução: {produtos_originais - produtos_normalizados} produtos")
                
                # Mostra produtos mais vendidos (por quantidade)
                print(f"\nTop 10 produtos por quantidade total:")
                top_produtos = df_final.groupby('produto_normalizado').agg({
                    'quantidade': 'sum',
                    'entrada': 'sum',
                    'data': 'count'
                }).sort_values('quantidade', ascending=False).head(10)
                
                for i, (produto, row) in enumerate(top_produtos.iterrows(), 1):
                    print(f"  {i:2d}. {produto[:50]}... - Qtd: {row['quantidade']:.0f}, Vendas: R$ {row['entrada']:.2f}")
                
                return True
            else:
                print(f"❌ Colunas de quantidade e produto normalizado não foram criadas")
                return False
        else:
            print(f"❌ DataFrame vazio após leitura")
            return False
        
    except Exception as e:
        print(f"❌ Erro no teste: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_specific_products():
    """Testa produtos específicos que aparecem múltiplas vezes"""
    
    print("\n=== TESTE DE PRODUTOS ESPECÍFICOS ===")
    
    filename = 'Backend/data/Planilha_Entradas.xls'
    
    try:
        # Lê a planilha
        df_raw = pd.read_excel(filename)
        
        # Simula UploadFile
        with open(filename, 'rb') as f:
            content = f.read()
        
        upload_file = UploadFile(
            filename=filename,
            file=BytesIO(content)
        )
        
        # Processa
        from api.endpoints.data import _read_any_cashflow_table
        df_processed = _read_any_cashflow_table(upload_file, treat_outflow_layout=False)
        df_final = processar_dados(df_processed, filename)
        
        if 'produto_normalizado' in df_final.columns:
            # Procura por produtos que aparecem com diferentes quantidades
            produtos_com_variacoes = []
            
            for produto in df_final['produto_normalizado'].unique():
                if pd.isna(produto) or produto == '':
                    continue
                    
                vendas_produto = df_final[df_final['produto_normalizado'] == produto]
                quantidades_unicas = vendas_produto['quantidade'].nunique()
                
                if quantidades_unicas > 1 and len(vendas_produto) > 1:
                    produtos_com_variacoes.append({
                        'produto': produto,
                        'vendas': len(vendas_produto),
                        'quantidades': sorted(vendas_produto['quantidade'].unique()),
                        'total_quantidade': vendas_produto['quantidade'].sum(),
                        'total_vendas': vendas_produto['entrada'].sum()
                    })
            
            print(f"Produtos com diferentes quantidades encontrados: {len(produtos_com_variacoes)}")
            
            if produtos_com_variacoes:
                print(f"\nTop 5 produtos com variações de quantidade:")
                produtos_com_variacoes.sort(key=lambda x: x['vendas'], reverse=True)
                
                for i, produto_info in enumerate(produtos_com_variacoes[:5], 1):
                    print(f"  {i}. {produto_info['produto'][:50]}...")
                    print(f"     Vendas: {produto_info['vendas']}, Quantidades: {produto_info['quantidades']}")
                    print(f"     Total: {produto_info['total_quantidade']:.0f} unidades, R$ {produto_info['total_vendas']:.2f}")
                    print()
                
                return True
            else:
                print("Nenhum produto com variações de quantidade encontrado")
                return False
        else:
            print("Coluna produto_normalizado não encontrada")
            return False
            
    except Exception as e:
        print(f"Erro no teste específico: {e}")
        return False

if __name__ == "__main__":
    print("=== TESTE COM PLANILHA REAL DE ENTRADAS ===")
    
    # Teste principal
    success1 = test_real_entradas()
    
    # Teste de produtos específicos
    success2 = test_specific_products()
    
    if success1 and success2:
        print("\n🎉 TESTES COM PLANILHA REAL CONCLUÍDOS COM SUCESSO!")
        print("✅ A normalização de produtos está funcionando com dados reais")
        print("✅ Produtos com diferentes quantidades são reconhecidos corretamente")
        print("✅ O sistema está pronto para simulações mais precisas")
    else:
        print("\n❌ Alguns testes falharam")
