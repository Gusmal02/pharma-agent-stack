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

# Instancia base del LLM
llm = ChatOllama(
    base_url=OLLAMA_URL,
    model=MODELO,
    temperature=0.0,
)

# Instancia vinculada a herramientas para la primera llamada
llm_with_tools = llm.bind_tools(tools_catálogo)

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
7. Cuando presentes resultados analíticos, traduce los números en recommendations de negocio claras. Si el R² es menor a 0.4, indica explícitamente que la tendencia no es concluyente y no hagas proyecciones con falsa confianza.

GENERAL:
8. Responde siempre en español de México, de forma humana y profesional.
9. Nunca respondas "no puedo ayudarte" si la pregunta es sobre medicamentos — siempre hay una herramienta disponible.
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

# Palabras clave para fallback cuando el LLM no emite tool_call
KEYWORDS_TOOLS = {
    "predecir_demanda_futura": [
        "tendencia", "proyección", "proyeccion", "demanda futura",
        "va a subir", "va a bajar", "creciendo", "bajando",
        "próximos meses", "proximos meses", "forecast",
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
            if tool_name in ("predecir_demanda_futura", "verificar_riesgo_desabasto"):
                return tool_name, {"nombre_medicamento": med}
            if tool_name == "verificar_stock":
                return tool_name, {"nombre_medicamento": med}
            if tool_name == "consultar_manual_conocimiento":
                return tool_name, {"tema": texto_lower}
    return None, {}


class PharmaAgentExecutor:
    def __init__(self, chain, tools, base_llm):
        self.chain = chain
        self.tools_map = {tool.name: tool for tool in tools}
        self.base_llm = base_llm

    def invoke(self, inputs: dict) -> dict:
        input_original = inputs["input"]
        chat_history = inputs.get("chat_history", [])

        # Primera llamada al LLM con soporte de herramientas
        ai_msg = self.chain.invoke(inputs)
        content = ai_msg.content.strip() if ai_msg.content else ""

        tool_name = None
        tool_args = {}

        # Intento 1: tool_calls nativo del LLM
        if ai_msg.tool_calls:
            tool_name = ai_msg.tool_calls[0]["name"]
            tool_args = ai_msg.tool_calls[0]["args"]
        else:
            # Intento 2: JSON embebido en el texto
            match = re.search(r"\{.*?\}", content, re.DOTALL)
            if match:
                try:
                    datos_json = json.loads(match.group(0))
                    if "name" in datos_json:
                        tool_name = datos_json.get("name")
                        tool_args = datos_json.get("arguments", {})
                except Exception:
                    pass

        # Intento 3: fallback por palabras clave
        if not tool_name:
            tool_name, tool_args = _fallback_por_keywords(input_original)
            if tool_name:
                print(f"\n[FALLBACK] Herramienta inferida por keywords: {tool_name}")

        # Bloque de ejecución e interpolación de herramientas
        if tool_name:
            print(f"\n[AGENTE] Ejecutando: {tool_name} | args: {tool_args}")

            if tool_name in self.tools_map:
                resultado = self.tools_map[tool_name].invoke(tool_args)
            else:
                resultado = f"Herramienta '{tool_name}' no disponible."

            # Reestructuramos el prompt de síntesis de forma hiperestricta
            prompt_sintesis = ChatPromptTemplate.from_messages([
                ("system", (
                    "Eres 'PharmaBot', un asistente farmacéutico experto y humano.\n"
                    "INSTRUCCIÓN: Responde la duda del usuario basándote únicamente en el resultado interno.\n"
                    "Escribe de forma puramente conversacional, en texto plano, sin código y sin estructurar JSON."
                )),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", (
                    f"Resultado interno de la consulta: {resultado}\n"
                    f"Petición original del usuario: {input_original}"
                ))
            ])

            cadena_sintesis = prompt_sintesis | self.base_llm
            ai_msg_final = cadena_sintesis.invoke({"chat_history": chat_history})
            respuesta_cruda = ai_msg_final.content.strip()

            # --- BLINDAJE ANTI-JSON INTERNO ---
            # Si el modelo necio vuelve a escupir llaves, parseamos y generamos la respuesta directo en Python
            match_json_salida = re.search(r"\{.*?\}", respuesta_cruda, re.DOTALL)
            if match_json_salida:
                try:
                    # Si el resultado interno contiene "RECHAZO" o es un string directo de rechazo
                    if "rechazo" in str(resultado).lower() or "no coincide" in str(resultado).lower():
                        return {
                            "output": (
                                f"Lo siento, pero no puedo autorizar la venta de {tool_args.get('nombre_medicamento_solicitado', 'el medicamento')}. "
                                f"El sistema de validación médica arrojó un rechazo para el folio {tool_args.get('codigo_receta', '')}. "
                                "Por favor, verifica tus datos o consulta con tu médico."
                            )
                        }
                    else:
                        return {"output": f"Validación completada con éxito. El sistema reporta: {resultado}"}
                except Exception:
                    pass

            return {"output": respuesta_cruda}

        # Conversación general si no se detectó ninguna herramienta
        if content and "no puedo" not in content.lower():
            return {"output": content}

        return {
            "output": (
                "Disculpa, no entendí bien tu pregunta. "
                "Puedo ayudarte con: precios y disponibilidad, "
                "validación de recetas, información del manual técnico, "
                "tendencias de demanda y riesgo de desabasto."
            )
        }


# Pasamos la instancia limpia 'llm' como tercer argumento
agent_executor = PharmaAgentExecutor(agent_chain, tools_catálogo, llm)