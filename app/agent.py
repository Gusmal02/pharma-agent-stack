# app/agent.py
import os
import json
import re
import logging
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from app.tools import tools_catálogo

load_dotenv()
logger = logging.getLogger(__name__)

# ── Detección automática de LLM disponible ───────────────────────────────────
def _inicializar_llm():
    gcp_key = os.getenv("GOOGLE_API_KEY")
    gcp_project = os.getenv("GCP_PROJECT_ID")

    if gcp_key or gcp_project:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            llm = ChatGoogleGenerativeAI(
                model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
                temperature=0.0,
                google_api_key=gcp_key,
                client_options={"api_endpoint": "generativelanguage.googleapis.com"},
                transport="rest",
            )
            logger.info("LLM: Gemini API activo.")
            return llm, True
        except Exception as e:
            logger.warning(f"Gemini no disponible: {e}. Usando Ollama.")

    from langchain_ollama import ChatOllama
    llm = ChatOllama(
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        model=os.getenv("MODEL_NAME", "qwen2.5-coder:7b-instruct-q4_K_M"),
        temperature=0.0,
    )
    logger.info("LLM: Ollama local activo.")
    return llm, False


llm, USANDO_GEMINI = _inicializar_llm()
llm_with_tools = llm.bind_tools(tools_catálogo)

# ── Sistema de prompt ─────────────────────────────────────────────────────────
system_instruction = """Eres "PharmaBot", un asistente farmacéutico experto y Científico de Datos de Inventarios para una farmacia local.

REGLAS DE OPERACIÓN — sigue estas instrucciones sin excepción:

VENTAS Y STOCK:
1. Si el usuario pregunta por precios, disponibilidad o stock → invoca `verificar_stock`.

INFORMACIÓN MÉDICA Y MANUAL:
2. Si el usuario pregunta cómo usar un medicamento, cómo almacenarlo, dosis o contraindicaciones → invoca `consultar_manual_conocimiento`.

RECETAS MÉDICAS:
3. Si el medicamento requiere receta, exige el folio y usa `validar_receta_medica` pasando obligatoriamente el código de receta y el nombre del medicamento.
4. Si la herramienta devuelve RECHAZO o error de coincidencia → niega la venta de forma rotunda y explica el motivo.

ANALÍTICA PREDICTIVA E INVENTARIOS:
5. Si el usuario pregunta por tendencias, proyecciones, comportamiento futuro de ventas o si la demanda sube o baja → invoca `predecir_demanda_futura`.
6. Si el usuario pregunta cuándo se acaba el stock, riesgo de desabasto, cuándo comprar o si hay suficiente inventario → invoca `verificar_riesgo_desabasto`.
7. Cuando presentes resultados analíticos, traduce los números en recomendaciones de negocio claras. Si el R² es menor a 0.4, indica explícitamente que la tendencia no es concluyente.

GENERAL:
8. Responde siempre en español de México, de forma humana y profesional.
9. Nunca respondas "no puedo ayudarte" si la pregunta es sobre medicamentos.
"""

prompt_template = ChatPromptTemplate.from_messages([
    ("system", system_instruction),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
])

# ── Fallback por keywords ─────────────────────────────────────────────────────
KEYWORDS_TOOLS = {
    "validar_receta_medica": [
        "receta", "folio", "rec-", "validar", "comprar con receta",
        "quiero comprar", "adquirir", "vender", "venta de",
    ],
    "predecir_demanda_futura": [
        ...
    ],
    "verificar_riesgo_desabasto": [
        "desabasto", "se acaba", "cuándo se acaba", "cuando se acaba",
        "días de stock", "dias de stock", "riesgo", "abastecer",
        "cuándo comprar", "cuando comprar", "agotamiento",
    ],
    "consultar_manual_conocimiento": [
        "temperatura", "guardar", "almacenar", "almacenamiento",
        "dosis", "contraindicacion", "contraindicación",
        "cómo se usa", "como se usa", "efectos", "manual",
    ],
    "verificar_stock": [
        "precio", "costo", "cuánto cuesta", "cuanto cuesta",
        "tienen", "disponible", "stock", "hay ",
    ],
}

MEDICAMENTOS_CONOCIDOS = [
    "insulina", "paracetamol", "ibuprofeno", "amoxicilina",
    "clonazepam", "loratadina", "glargina",
]


def _extraer_medicamento(texto: str) -> str:
    texto_lower = texto.lower()
    for med in MEDICAMENTOS_CONOCIDOS:
        if med in texto_lower:
            return med
    return texto


def _fallback_por_keywords(texto: str):
    texto_lower = texto.lower()
    for tool_name, keywords in KEYWORDS_TOOLS.items():
        if any(kw in texto_lower for kw in keywords):
            med = _extraer_medicamento(texto_lower)
            if tool_name == "validar_receta_medica":
                match_receta = re.search(r"rec-[\w-]+", texto_lower)
                codigo = match_receta.group(0).upper() if match_receta else ""
                return tool_name, {
                    "codigo_receta": codigo,
                    "nombre_medicamento_solicitado": med
                }
            if tool_name in ("predecir_demanda_futura", "verificar_riesgo_desabasto"):
                return tool_name, {"nombre_medicamento": med}
            if tool_name == "verificar_stock":
                return tool_name, {"nombre_medicamento": med}
            if tool_name == "consultar_manual_conocimiento":
                return tool_name, {"tema": texto_lower}
    return None, {}


def _es_json_crudo(texto: str) -> bool:
    """Detecta si el texto es JSON crudo que no debería llegar al usuario."""
    texto = texto.strip()
    if not (texto.startswith("{") or texto.startswith("[")):
        return False
    try:
        json.loads(texto)
        return True
    except Exception:
        return False


def _sintetizar_resultado(resultado: str, input_original: str, chat_history: list, tool_args: dict) -> str:
    """Síntesis centralizada — usada tanto por LangGraph como por LangChain fallback."""
    prompt_sintesis = ChatPromptTemplate.from_messages([
        ("system", (
            "Eres 'PharmaBot', un asistente farmacéutico experto y humano.\n"
            "INSTRUCCIÓN ESTRICTA: Responde la duda del usuario basándote ÚNICAMENTE en el resultado interno.\n"
            "Escribe de forma puramente conversacional, en texto plano, en español de México.\n"
            "PROHIBIDO: JSON, llaves {{}}, corchetes [[]], código, markdown o cualquier formato estructurado.\n"
            "Si el resultado indica RECHAZO u OPERACIÓN RECHAZADA, comunícalo de forma clara y empática."
        )),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", (
            f"Resultado interno de la consulta:\n{resultado}\n\n"
            f"Petición original del usuario: {input_original}"
        ))
    ])

    ai_final = (prompt_sintesis | llm).invoke({"chat_history": chat_history})
    respuesta = ai_final.content.strip()

    # Blindaje final: si aún así sale JSON, construimos respuesta en Python
    if _es_json_crudo(respuesta):
        resultado_lower = resultado.lower()
        if "rechazado" in resultado_lower or "rechazo" in resultado_lower or "no coincide" in resultado_lower:
            med = tool_args.get("nombre_medicamento_solicitado", "el medicamento")
            receta = tool_args.get("codigo_receta", "")
            return (
                f"Lo siento, no puedo autorizar la venta de {med}. "
                f"El folio {receta} no coincide con el medicamento solicitado. "
                "Por favor verifica tus datos o consulta con tu médico."
            )
        return f"Consulta procesada. El sistema reporta: {resultado}"

    return respuesta


# ── LangGraph ─────────────────────────────────────────────────────────────────
try:
    from langgraph.graph import StateGraph, END
    from typing import TypedDict

    class AgentState(TypedDict):
        input: str
        chat_history: list
        tool_name: str
        tool_args: dict
        tool_result: str
        output: str

    def nodo_clasificar(state: AgentState) -> AgentState:
        """Nodo 1: El LLM decide qué herramienta usar."""
        ai_msg = (prompt_template | llm_with_tools).invoke({
            "input": state["input"],
            "chat_history": state["chat_history"]
        })

        tool_name = None
        tool_args = {}
        content = ai_msg.content.strip() if ai_msg.content else ""

        # Intento 1: tool_calls nativo
        if ai_msg.tool_calls:
            tool_name = ai_msg.tool_calls[0]["name"]
            tool_args = ai_msg.tool_calls[0]["args"]
        else:
            # Intento 2: JSON embebido en texto
            match = re.search(r"\{.*?\}", content, re.DOTALL)
            if match:
                try:
                    datos = json.loads(match.group(0))
                    if "name" in datos:
                        tool_name = datos.get("name")
                        tool_args = datos.get("arguments", {})
                except Exception:
                    pass

        # Intento 3: fallback por keywords
        if not tool_name:
            tool_name, tool_args = _fallback_por_keywords(state["input"])
            if tool_name:
                logger.info(f"[FALLBACK] Herramienta inferida: {tool_name}")

        return {
            **state,
            "tool_name": tool_name or "",
            "tool_args": tool_args,
            "output": ""  # Siempre vacío — síntesis en nodo_sintetizar
        }

    def nodo_ejecutar_tool(state: AgentState) -> AgentState:
        """Nodo 2: Ejecuta la herramienta seleccionada."""
        tools_map = {tool.name: tool for tool in tools_catálogo}
        tool_name = state["tool_name"]

        if tool_name in tools_map:
            logger.info(f"[AGENTE] Ejecutando: {tool_name} | args: {state['tool_args']}")
            resultado = tools_map[tool_name].invoke(state["tool_args"])
        else:
            resultado = f"Herramienta '{tool_name}' no disponible."

        return {**state, "tool_result": str(resultado)}

    def nodo_sintetizar(state: AgentState) -> AgentState:
        """Nodo 3: El LLM sintetiza la respuesta final."""
        respuesta = _sintetizar_resultado(
            resultado=state["tool_result"],
            input_original=state["input"],
            chat_history=state["chat_history"],
            tool_args=state["tool_args"]
        )
        return {**state, "output": respuesta}

    def nodo_respuesta_directa(state: AgentState) -> AgentState:
        """Nodo 4: Respuesta conversacional sin herramienta."""
        return {
            **state,
            "output": (
                "Disculpa, no entendí bien tu pregunta. "
                "Puedo ayudarte con: precios y disponibilidad, "
                "validación de recetas, información del manual técnico, "
                "tendencias de demanda y riesgo de desabasto."
            )
        }

    def decidir_ruta(state: AgentState) -> str:
        return "ejecutar_tool" if state["tool_name"] else "respuesta_directa"

    grafo = StateGraph(AgentState)
    grafo.add_node("clasificar", nodo_clasificar)
    grafo.add_node("ejecutar_tool", nodo_ejecutar_tool)
    grafo.add_node("sintetizar", nodo_sintetizar)
    grafo.add_node("respuesta_directa", nodo_respuesta_directa)

    grafo.set_entry_point("clasificar")
    grafo.add_conditional_edges("clasificar", decidir_ruta, {
        "ejecutar_tool": "ejecutar_tool",
        "respuesta_directa": "respuesta_directa"
    })
    grafo.add_edge("ejecutar_tool", "sintetizar")
    grafo.add_edge("sintetizar", END)
    grafo.add_edge("respuesta_directa", END)

    agent_graph = grafo.compile()
    USANDO_LANGGRAPH = True
    logger.info("LangGraph activo.")

except ImportError:
    agent_graph = None
    USANDO_LANGGRAPH = False
    logger.warning("LangGraph no instalado. Usando LangChain básico.")

# ── Ejecutor principal ────────────────────────────────────────────────────────
agent_chain = (
    {
        "input": lambda x: x["input"],
        "chat_history": lambda x: x["chat_history"],
    }
    | prompt_template
    | llm_with_tools
)


class PharmaAgentExecutor:
    def invoke(self, inputs: dict) -> dict:
        if USANDO_LANGGRAPH and agent_graph:
            try:
                resultado = agent_graph.invoke({
                    "input": inputs["input"],
                    "chat_history": inputs.get("chat_history", []),
                    "tool_name": "",
                    "tool_args": {},
                    "tool_result": "",
                    "output": ""
                })
                return {"output": resultado["output"]}
            except Exception as e:
                logger.warning(f"LangGraph falló: {e}. Usando LangChain básico.")

        return self._invoke_langchain(inputs)

    def _invoke_langchain(self, inputs: dict) -> dict:
        """Lógica original como fallback."""
        input_original = inputs["input"]
        chat_history = inputs.get("chat_history", [])
        tools_map = {tool.name: tool for tool in tools_catálogo}

        ai_msg = agent_chain.invoke(inputs)
        content = ai_msg.content.strip() if ai_msg.content else ""

        tool_name = None
        tool_args = {}

        if ai_msg.tool_calls:
            tool_name = ai_msg.tool_calls[0]["name"]
            tool_args = ai_msg.tool_calls[0]["args"]
        else:
            match = re.search(r"\{.*?\}", content, re.DOTALL)
            if match:
                try:
                    datos = json.loads(match.group(0))
                    if "name" in datos:
                        tool_name = datos.get("name")
                        tool_args = datos.get("arguments", {})
                except Exception:
                    pass

        if not tool_name:
            tool_name, tool_args = _fallback_por_keywords(input_original)

        if tool_name and tool_name in tools_map:
            resultado = tools_map[tool_name].invoke(tool_args)
            return {
                "output": _sintetizar_resultado(
                    resultado=str(resultado),
                    input_original=input_original,
                    chat_history=chat_history,
                    tool_args=tool_args
                )
            }

        if content and not _es_json_crudo(content) and "no puedo" not in content.lower():
            return {"output": content}

        return {
            "output": (
                "Disculpa, no entendí bien tu pregunta. "
                "Puedo ayudarte con: precios y disponibilidad, "
                "validación de recetas, información del manual técnico, "
                "tendencias de demanda y riesgo de desabasto."
            )
        }


agent_executor = PharmaAgentExecutor()