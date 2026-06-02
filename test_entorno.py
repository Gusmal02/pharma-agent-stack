# test_entorno.py
import os
from dotenv import load_dotenv
import fastapi
import langchain
import pydantic

# Cargamos las variables del archivo .env
load_dotenv()

print("\n=== VERIFICACIÓN DE ENTORNO EN PAVILION ===")
print(f"Versión de FastAPI:  {fastapi.__version__}")
print(f"Versión de Pydantic: {pydantic.__version__}")
print(f"Versión de LangChain: {langchain.__version__}")
print(f"Variable OLLAMA_BASE_URL: '{os.getenv('OLLAMA_BASE_URL')}'")
print(f"Variable MODEL_NAME:     '{os.getenv('MODEL_NAME')}'")
print("===========================================")
print("¡Felicidades, Gustavo! Tu entorno local está 100% operativo.\n")