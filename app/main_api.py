# app/main_api.py
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
from app.agent import agent_executor
# --- IMPORTA LOS TIPOS DE MENSAJE ---
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

app = FastAPI(
    title="PharmaBot API",
    description="API para interactuar con el agente inteligente de la farmacia",
    version="1.0.0"
)

class ChatRequest(BaseModel):
    input: str
    chat_history: List[Dict[str, Any]] = []

class ChatResponse(BaseModel):
    output: str

@app.get("/")
def read_root():
    return {"status": "online", "agent": "PharmaBot"}

@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    try:
        # Reconstruimos el historial de diccionarios a objetos de LangChain
        formatted_history = []
        for msg in request.chat_history:
            # Soportamos formatos comunes: 'role'/'content' o 'type'/'text'
            role = msg.get("role") or msg.get("type")
            content = msg.get("content") or msg.get("text", "")
            
            if role in ["user", "human", "HumanMessage"]:
                formatted_history.append(HumanMessage(content=content))
            elif role in ["assistant", "ai", "AIMessage"]:
                formatted_history.append(AIMessage(content=content))
            elif role in ["system", "SystemMessage"]:
                formatted_history.append(SystemMessage(content=content))

        # Invocamos al agente pasándole el historial correctamente formateado
        response = agent_executor.invoke({
            "input": request.input,
            "chat_history": formatted_history
        })
        return ChatResponse(output=response["output"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))