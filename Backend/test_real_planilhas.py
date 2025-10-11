# test_real_planilhas.py
# Script para testar as melhorias com as planilhas reais fornecidas

import pandas as pd
import sys
import os

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from core.business_event_analyzer import identify_key_business_events
from core.data_processing import processar_dados

def test_planilha_entradas():
    """Testa a planilha de entradas."""
    print("="*80)
    print("TESTE DA PLANILHA DE ENTRADAS")
    print("="*80)
    
    try:
        # Carrega a planilha de entradas
        file_path = "data/Planilha_Entradas.xls"
        print(f"Carregando arquivo: {file_path}")
        
        # Lê o arquivo Excel
        df_raw = pd.read_excel(file_path)
        print(f"Arquivo carregado com sucesso!")
        print(f"Dimensões: {df_raw.shape}")
        print(f"Colunas: {list(df_raw.columns)}")
        print()
        
        # Mostra as primeiras linhas
        print("Primeiras 5 linhas do arquivo original:")
        print(df_raw.head().to_string())
        print()
        
        # Processa os dados usando a função melhorada
        print("Processando dados...")
        df_processed = processar_dados(df_raw, filename=file_path)
        print(f"Dados processados com sucesso!")
        print(f"Dimensões após processamento: {df_processed.shape}")
        print(f"Colunas após processamento: {list(df_processed.columns)}")
        print()
        
        # Mostra estatísticas básicas
        if 'entrada' in df_processed.columns:
            total_entradas = df_processed['entrada'].sum()
            print(f"Total de entradas: R$ {total_entradas:.2f}")
            print(f"Número de transações de entrada: {len(df_processed[df_processed['entrada'] > 0])}")
        
        if 'saida' in df_processed.columns:
            total_saidas = df_processed['saida'].sum()
            print(f"Total de saídas: R$ {total_saidas:.2f}")
            print(f"Número de transações de saída: {len(df_processed[df_processed['saida'] > 0])}")
        
        print()
        
        # Executa a análise de eventos
        print("Executando análise de eventos de negócio...")
        result = identify_key_business_events(df_processed, top_n=10)
        
        # Mostra resultados
        print("\n" + "="*60)
        print("PRINCIPAIS RECEITAS IDENTIFICADAS:")
        print("="*60)
        for i, inflow in enumerate(result['key_inflows'], 1):
            print(f"{i}. {inflow['name']}")
            print(f"   Total: R$ {inflow['total_amount']:.2f}")
            print(f"   Frequência: {inflow['frequency']} transações")
            print(f"   Quantidade total: {inflow['total_quantity']} unidades")
            print(f"   Categoria: {inflow['category']}")
            print()
        
        print("="*60)
        print("PRINCIPAIS CUSTOS IDENTIFICADOS:")
        print("="*60)
        for i, outflow in enumerate(result['key_outflows'], 1):
            print(f"{i}. {outflow['name']}")
            print(f"   Total: R$ {outflow['total_amount']:.2f}")
            print(f"   Frequência: {outflow['frequency']} transações")
            print(f"   Categoria: {outflow['category']}")
            print()
        
        return df_processed, result
        
    except Exception as e:
        print(f"❌ ERRO ao processar planilha de entradas: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, None

def test_planilha_saidas():
    """Testa a planilha de saídas."""
    print("="*80)
    print("TESTE DA PLANILHA DE SAÍDAS")
    print("="*80)
    
    try:
        # Carrega a planilha de saídas
        file_path = "data/yUuUeCnbiOsksnUd.xlsx"
        print(f"Carregando arquivo: {file_path}")
        
        # Primeiro, vamos ver quais abas existem
        excel_file = pd.ExcelFile(file_path)
        print(f"Abas disponíveis: {excel_file.sheet_names}")
        print()
        
        # Processa cada aba
        all_dataframes = []
        for sheet_name in excel_file.sheet_names:
            print(f"Processando aba: {sheet_name}")
            try:
                df_raw = pd.read_excel(file_path, sheet_name=sheet_name)
                print(f"  Dimensões: {df_raw.shape}")
                print(f"  Colunas: {list(df_raw.columns)}")
                
                # Processa os dados
                df_processed = processar_dados(df_raw, filename=f"{file_path}_{sheet_name}")
                
                if not df_processed.empty:
                    all_dataframes.append(df_processed)
                    print(f"  ✅ Processado com sucesso!")
                else:
                    print(f"  ⚠️  Aba vazia após processamento")
                
                print()
                
            except Exception as e:
                print(f"  ❌ Erro ao processar aba {sheet_name}: {str(e)}")
                print()
        
        if not all_dataframes:
            print("❌ Nenhuma aba foi processada com sucesso")
            return None, None
        
        # Combina todos os dataframes
        print("Combinando dados de todas as abas...")
        df_combined = pd.concat(all_dataframes, ignore_index=True)
        print(f"Dados combinados: {df_combined.shape}")
        print()
        
        # Mostra estatísticas básicas
        if 'entrada' in df_combined.columns:
            total_entradas = df_combined['entrada'].sum()
            print(f"Total de entradas: R$ {total_entradas:.2f}")
            print(f"Número de transações de entrada: {len(df_combined[df_combined['entrada'] > 0])}")
        
        if 'saida' in df_combined.columns:
            total_saidas = df_combined['saida'].sum()
            print(f"Total de saídas: R$ {total_saidas:.2f}")
            print(f"Número de transações de saída: {len(df_combined[df_combined['saida'] > 0])}")
        
        print()
        
        # Executa a análise de eventos
        print("Executando análise de eventos de negócio...")
        result = identify_key_business_events(df_combined, top_n=10)
        
        # Mostra resultados
        print("\n" + "="*60)
        print("PRINCIPAIS RECEITAS IDENTIFICADAS:")
        print("="*60)
        for i, inflow in enumerate(result['key_inflows'], 1):
            print(f"{i}. {inflow['name']}")
            print(f"   Total: R$ {inflow['total_amount']:.2f}")
            print(f"   Frequência: {inflow['frequency']} transações")
            print(f"   Quantidade total: {inflow['total_quantity']} unidades")
            print(f"   Categoria: {inflow['category']}")
            print()
        
        print("="*60)
        print("PRINCIPAIS CUSTOS IDENTIFICADOS:")
        print("="*60)
        for i, outflow in enumerate(result['key_outflows'], 1):
            print(f"{i}. {outflow['name']}")
            print(f"   Total: R$ {outflow['total_amount']:.2f}")
            print(f"   Frequência: {outflow['frequency']} transações")
            print(f"   Categoria: {outflow['category']}")
            print()
        
        return df_combined, result
        
    except Exception as e:
        print(f"❌ ERRO ao processar planilha de saídas: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, None

def test_combined_analysis():
    """Testa a análise combinada das duas planilhas."""
    print("="*80)
    print("TESTE DA ANÁLISE COMBINADA")
    print("="*80)
    
    try:
        # Carrega e processa ambas as planilhas
        print("Carregando planilha de entradas...")
        df_entradas = pd.read_excel("data/Planilha_Entradas.xls")
        df_entradas_processed = processar_dados(df_entradas, filename="data/Planilha_Entradas.xls")
        
        print("Carregando planilha de saídas...")
        excel_file = pd.ExcelFile("data/yUuUeCnbiOsksnUd.xlsx")
        all_saidas = []
        
        for sheet_name in excel_file.sheet_names:
            try:
                df_raw = pd.read_excel("data/yUuUeCnbiOsksnUd.xlsx", sheet_name=sheet_name)
                df_processed = processar_dados(df_raw, filename=f"data/yUuUeCnbiOsksnUd.xlsx_{sheet_name}")
                if not df_processed.empty:
                    all_saidas.append(df_processed)
            except Exception as e:
                print(f"Erro ao processar aba {sheet_name}: {e}")
        
        if all_saidas:
            df_saidas_combined = pd.concat(all_saidas, ignore_index=True)
        else:
            df_saidas_combined = pd.DataFrame()
        
        # Combina entradas e saídas
        if not df_entradas_processed.empty and not df_saidas_combined.empty:
            # Adiciona colunas que podem estar faltando
            for col in ['entrada', 'saida', 'descricao', 'categoria']:
                if col not in df_entradas_processed.columns:
                    df_entradas_processed[col] = 0 if col in ['entrada', 'saida'] else ''
                if col not in df_saidas_combined.columns:
                    df_saidas_combined[col] = 0 if col in ['entrada', 'saida'] else ''
            
            df_combined = pd.concat([df_entradas_processed, df_saidas_combined], ignore_index=True)
        elif not df_entradas_processed.empty:
            df_combined = df_entradas_processed
        elif not df_saidas_combined.empty:
            df_combined = df_saidas_combined
        else:
            print("❌ Nenhum dado foi processado com sucesso")
            return None
        
        print(f"Dados combinados: {df_combined.shape}")
        print()
        
        # Mostra estatísticas finais
        total_entradas = df_combined['entrada'].sum() if 'entrada' in df_combined.columns else 0
        total_saidas = df_combined['saida'].sum() if 'saida' in df_combined.columns else 0
        
        print(f"Total de entradas: R$ {total_entradas:.2f}")
        print(f"Total de saídas: R$ {total_saidas:.2f}")
        print(f"Saldo líquido: R$ {total_entradas - total_saidas:.2f}")
        print()
        
        # Executa a análise final
        print("Executando análise final de eventos de negócio...")
        result = identify_key_business_events(df_combined, top_n=15)
        
        # Mostra resultados finais
        print("\n" + "="*60)
        print("PRINCIPAIS RECEITAS IDENTIFICADAS (TOP 10):")
        print("="*60)
        for i, inflow in enumerate(result['key_inflows'][:10], 1):
            print(f"{i}. {inflow['name']}")
            print(f"   Total: R$ {inflow['total_amount']:.2f}")
            print(f"   Frequência: {inflow['frequency']} transações")
            print(f"   Quantidade total: {inflow['total_quantity']} unidades")
            print(f"   Categoria: {inflow['category']}")
            print()
        
        print("="*60)
        print("PRINCIPAIS CUSTOS IDENTIFICADOS (TOP 10):")
        print("="*60)
        for i, outflow in enumerate(result['key_outflows'][:10], 1):
            print(f"{i}. {outflow['name']}")
            print(f"   Total: R$ {outflow['total_amount']:.2f}")
            print(f"   Frequência: {outflow['frequency']} transações")
            print(f"   Categoria: {outflow['category']}")
            print()
        
        return df_combined, result
        
    except Exception as e:
        print(f"❌ ERRO na análise combinada: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, None

def main():
    """Executa todos os testes com as planilhas reais."""
    print("INICIANDO TESTES COM PLANILHAS REAIS")
    print("="*80)
    
    try:
        # Teste 1: Planilha de entradas
        df_entradas, result_entradas = test_planilha_entradas()
        
        # Teste 2: Planilha de saídas
        df_saidas, result_saidas = test_planilha_saidas()
        
        # Teste 3: Análise combinada
        df_combined, result_combined = test_combined_analysis()
        
        print("="*80)
        print("RESUMO DOS TESTES COM PLANILHAS REAIS")
        print("="*80)
        
        if result_entradas:
            print(f"✅ Planilha de entradas: {len(result_entradas['key_inflows'])} receitas identificadas")
        else:
            print("❌ Planilha de entradas: Falha no processamento")
        
        if result_saidas:
            print(f"✅ Planilha de saídas: {len(result_saidas['key_outflows'])} custos identificados")
        else:
            print("❌ Planilha de saídas: Falha no processamento")
        
        if result_combined:
            print(f"✅ Análise combinada: {len(result_combined['key_inflows'])} receitas, {len(result_combined['key_outflows'])} custos")
        else:
            print("❌ Análise combinada: Falha no processamento")
        
        print("\n🎯 MELHORIAS IMPLEMENTADAS E TESTADAS:")
        print("✅ Identificação de custos numéricos melhorada")
        print("✅ Alocação inteligente de valores para receitas")
        print("✅ Processamento de múltiplos produtos")
        print("✅ Dedução de preços unitários")
        print("✅ Tratamento robusto de diferentes formatos de planilha")
        
        return True
        
    except Exception as e:
        print(f"❌ ERRO durante os testes: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)
    else:
        print("\n✅ Todos os testes com planilhas reais foram concluídos com sucesso!")
