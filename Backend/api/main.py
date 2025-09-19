# Backend/api/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import sys

#Comando para rodar a api:
#python -m uvicorn Backend.api.main:app --reload --port 8000

# Adiciona o diretório raiz ao path para encontrar os outros módulos
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importar os 'routers' de cada arquivo de endpoint
from api.endpoints.data import router as data_router
from api.endpoints.predictions import router as predictions_router
from api.endpoints.simulations import router as simulations_router


# Criar a aplicação FastAPI
app = FastAPI(
    title="Simple.Tech API",
    description="API para análise de risco, previsão de fluxo de caixa e simulação de cenários.",
    version="1.0.0"
)

# Configurar o CORS para permitir que o Streamlit (rodando em outra porta) se conecte
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite todas as origens, ideal para desenvolvimento local
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir os routers dos endpoints na aplicação principal
app.include_router(data_router, prefix="/api/data", tags=["Data Management"])
app.include_router(predictions_router, prefix="/api/predictions", tags=["Predictions & Alerts"])
app.include_router(simulations_router, prefix="/api/simulations", tags=["Simulations"])


# --- Endpoints Principais ---

@app.get("/", tags=["Root"])
async def read_root():
    """Endpoint raiz que mostra que a API está funcionando."""
    return {
        "message": "Simple.Tech API está funcionando!",
        "docs_url": "/docs"
    }

@app.get("/health", tags=["Health Check"])
async def health_check():
    """Endpoint de 'saúde' para verificar se a API está online."""
    return {"status": "healthy"}

# --- Bloco para execução direta do arquivo (para testes) ---
if __name__ == "__main__":
    import uvicorn
    print("Iniciando servidor Uvicorn para Simple.Tech API em http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)