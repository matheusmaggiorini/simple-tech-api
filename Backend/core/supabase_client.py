# Backend/core/supabase_client.py

#import os
#from supabase import create_client, Client
#from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
#load_dotenv()

#url: str = os.environ.get("SUPABASE_URL")
#ey: str = os.environ.get("SUPABASE_KEY")

# Verifica se as variáveis foram carregadas
#if not url or not key:
#    raise EnvironmentError("As variáveis de ambiente SUPABASE_URL e SUPABASE_KEY não foram definidas.")

# Cria o cliente Supabase
#supabase: Client = create_client(url, key)

#print("Cliente Supabase inicializado com sucesso.")

supabase = None