# app/agent.py
import os
import json
import re
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from app.tools import tools_catálogo

load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
MODELO = os.getenv("MODEL_NAME", "qwen2.5-coder:7b-instruct-q4_K_M")

llm = ChatOllama(
    base_url=OLLAMA_URL,
    model=MODELO,
    temperature=0.0,
)

llm_with_tools = llm.bind_tools(tools_catálogo)

system_instruction = """Eres "PharmaBot", un asistente virtual avanzado para una farmacia local.

REGLAS DE OPERACIÓN CRÍTICAS:
1. Si el usuario pregunta por precios o disponibilidad (stock), invoca inmediatamente `verificar_stock`.
2. Si el usuario pregunta cómo usar un medicamento, cómo almacenarlo o tiene dudas de salud, invoca `consultar_manual_conocimiento`.
3. Si el medicamento requiere receta, exige el folio y usa `validar_receta_medica`. Debes pasar obligatoriamente tanto el código de la receta como el nombre del medicamento que el usuario desea comprar.
4. Si la herramienta devuelve un mensaje de RECHAZO o indica que los medicamentos no coinciden, niega la venta de forma rotunda y explica el motivo.
5. Responde de manera humana, profesional y precisa en Español de México.
"""

prompt_template = ChatPromptTemplate.from_messages([
    ("system", system_instruction),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
])

agent_chain = (
    {
        "input": lambda x: x["input"],
        "chat_history": lambda x: x["chat_history"],
    }
    | prompt_template
    | llm_with_tools
)


class PharmaAgentExecutor:
    def __init__(self, chain, tools):
        self.chain = chain
        self.tools_map = {tool.name: tool for tool in tools}

    def invoke(self, inputs: dict) -> dict:
        input_original = inputs["input"]
        chat_history = inputs.get("chat_history", [])

        ai_msg = self.chain.invoke(inputs)
        content = ai_msg.content.strip() if ai_msg.content else ""

        tool_name = None
        tool_args = {}

        if ai_msg.tool_calls:
            tool_name = ai_msg.tool_calls[0]["name"]
            tool_args = ai_msg.tool_calls[0]["args"]
        else:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                try:
                    datos_json = json.loads(match.group(0))
                    if "name" in datos_json:
                        tool_name = datos_json.get("name")
                        tool_args = datos_json.get("arguments", {})
                except Exception:
                    pass

        if tool_name:
            print(f"\n[AGENTE] Herramienta invocada: {tool_name} | args: {tool_args}")

            if tool_name in self.tools_map:
                resultado = self.tools_map[tool_name].invoke(tool_args)
            else:
                resultado = f"Herramienta '{tool_name}' no disponible."

            prompt_con_contexto = (
                f"Petición original del usuario: \"{input_original}\"\n\n"
                f"Resultado de la consulta interna:\n{resultado}\n\n"
                "REGLA CRÍTICA: Si el resultado indica RECHAZO o error de coincidencia, "
                "niega la venta de manera educada pero firme. "
                "Responde en español de México en TEXTO PLANO. Prohibido usar JSON."
            )

            # Se construye un nuevo dict limpio; nunca se muta el original.
            inputs_segunda_llamada = {
                "input": prompt_con_contexto,
                "chat_history": chat_history,
            }

            ai_msg_final = self.chain.invoke(inputs_segunda_llamada)
            return {"output": ai_msg_final.content}

        # Si el LLM respondió directamente sin usar herramienta
        return {"output": content}


agent_executor = PharmaAgentExecutor(agent_chain, tools_catálogo)