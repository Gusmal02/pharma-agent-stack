# test_entorno.py
import os
from dotenv import load_dotenv
import fastapi
import langchain
import pydantic
import langgraph

load_dotenv()

print("\n=== VERIFICACIÓN DE ENTORNO — PHARMA AGENT STACK ===")
print(f"FastAPI:   {fastapi.__version__}")
print(f"Pydantic:  {pydantic.__version__}")
print(f"LangChain: {langchain.__version__}")

# Verificar LangGraph
# Verificar LangGraph
try:
    
    from langgraph.graph import StateGraph
    print(f"LangGraph: instalado ✓")
except ImportError:
    print("LangGraph: NO instalado ✗")

# Verificar GCP
try:
    import vertexai
    print(f"Vertex AI: {vertexai.__version__} ✓")
except ImportError:
    print("Vertex AI SDK: NO instalado ✗")

print("\n--- Variables de entorno ---")
print(f"OLLAMA_BASE_URL:  '{os.getenv('OLLAMA_BASE_URL', 'no configurado')}'")
print(f"MODEL_NAME:       '{os.getenv('MODEL_NAME', 'no configurado')}'")
print(f"GCP_PROJECT_ID:   '{os.getenv('GCP_PROJECT_ID', 'pendiente — normal si no tienes cuenta aún')}'")
print(f"GEMINI_MODEL:     '{os.getenv('GEMINI_MODEL', 'no configurado')}'")
print(f"VERTEX_INDEX_ID:  '{os.getenv('VERTEX_INDEX_ID', 'pendiente')}'")

print("\n--- Estado del sistema ---")
gcp_listo = bool(os.getenv("GCP_PROJECT_ID") and os.getenv("GOOGLE_API_KEY"))
print(f"Modo activo: {'GCP (Gemini + Vertex AI)' if gcp_listo else 'Local (Ollama)'}")
print("====================================================\n")