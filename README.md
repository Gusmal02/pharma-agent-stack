# Pharma-Agent-Stack

Sistema agéntico local para automatización de pedidos farmacéuticos con IA — construido sin APIs de nube.

> **Estado:** En desarrollo activo — Fase 1 (Core Agent + RAG + API REST) funcional.

---

## ¿De qué trata este proyecto?

Las farmacias y distribuidoras del sector salud manejan medicamentos controlados, recetas digitales y manuales técnicos de almacenamiento. Automatizar ese flujo con IA es complejo porque **los datos son sensibles y no pueden salir de la infraestructura interna**.

Este proyecto resuelve ese problema: un agente de IA que corre 100% en local, consulta una base de datos real, valida recetas médicas y recupera información técnica de manuales — todo sin depender de OpenAI, Anthropic ni ningún servicio de nube.

---

## Demo rápido

**Consulta del manual técnico (RAG):**
```bash
curl -X POST http://127.0.0.1:8085/chat \
     -H "Content-Type: application/json" \
     -d '{"input": "A qué temperatura debo guardar la insulina en casa?", "chat_history": []}'
```
```json
{
  "output": "La insulina sin abrir debe conservarse entre 2°C y 8°C en refrigeración. Una vez abierta, puede mantenerse a temperatura ambiente entre 15°C y 30°C por un máximo de 28 días..."
}
```

**Intento de uso fraudulento de receta:**
```bash
curl -X POST http://127.0.0.1:8085/chat \
     -H "Content-Type: application/json" \
     -d '{"input": "Quiero comprar Insulina con la receta REC-9988-77", "chat_history": []}'
```
```json
{
  "output": "No puedo procesar esta venta. La receta REC-9988-77 es válida, pero autoriza exclusivamente Amoxicilina 500mg para el paciente Carlos López Mendoza. No puede utilizarse para adquirir Insulina."
}
```

---

## Stack tecnológico

| | |
|---|---|
| **LLM local** | Qwen2.5-Coder 7B via Ollama (sin APIs externas) |
| **Agente** | LangChain + Tool-Calling + fallback por keywords |
| **API** | FastAPI + Uvicorn + Pydantic v2 |
| **Base de datos** | SQLite + SQLAlchemy 2.0 |
| **RAG** | Motor propio sobre Markdown (sin ChromaDB en Fase 1) |
| **Infra** | Docker (Fase 2) · Kubernetes con StatefulSet (Fase 3) |

---

## Arquitectura
Usuario
│
▼
FastAPI  ──►  PharmaAgentExecutor  ──►  LLM local (Ollama)
│
┌──────────┼──────────┐
▼          ▼          ▼
verificar   validar    consultar
_stock     _receta     _manual
(SQLite)   (SQLite)   (RAG/MD)

El agente recibe lenguaje natural, decide qué herramienta invocar, ejecuta la consulta contra datos reales y formula una respuesta. Si el LLM cuantizado no emite un `tool_call` estructurado, un fallback por palabras clave garantiza que la herramienta correcta se ejecute de todas formas.

---

## Problemas reales que resolví durante el desarrollo

Esto no fue seguir un tutorial. Estos son los bugs que encontré y cómo los resolví:

**Fuga de conexiones en la base de datos** — El patrón original dejaba sesiones de SQLAlchemy abiertas cuando ocurría una excepción, agotando el pool silenciosamente. Lo corregí con `@contextmanager` y `try/finally` para garantizar el cierre en cualquier ruta de ejecución.

**El LLM respondía "no puedo ayudarte" en lugar de usar sus herramientas** — Los modelos cuantizados a 4 bits no siempre emiten `tool_calls` estructurados. Implementé un mecanismo de fallback por palabras clave que detecta la intención del usuario e invoca la herramienta correcta aunque el modelo responda en texto plano.

**Ruta del archivo RAG rota en producción** — La ruta `knowledge/insulina.md` era relativa al directorio de trabajo, que cambia según desde dónde se lanza uvicorn. Lo corregí usando `Path(__file__).resolve().parent` para resolver la ruta de forma absoluta desde la ubicación del archivo fuente.

**Historial de conversación corrompido entre llamadas al LLM** — El orquestador mutaba el dict `inputs` original antes de la segunda llamada, sobreescribiendo el `chat_history`. Lo corregí construyendo un dict nuevo para cada invocación sin tocar el original.

---

## Estructura del proyecto

```text
pharma-agent-stack/
├── app/
│   ├── agent.py           # Orquestador: prompts, tool-calling, fallback por keywords
│   ├── database.py        # Configuración SQLAlchemy + SessionLocal
│   ├── main.py            # Interfaz CLI interactiva
│   ├── main_api.py        # API REST con FastAPI
│   ├── rag_utils.py       # Motor RAG: segmentación Markdown y recuperación
│   ├── tools.py           # Herramientas del agente (Stock, Recetas, RAG)
│   ├── knowledge/
│   │   └── insulina.md    # Base de conocimiento técnica (Vademécum)
│   └── models/
│       └── pharma.py      # Modelos SQLAlchemy: Medicamento, RecetaDigital
├── .env                   # Variables de entorno (no incluido en git)
├── docker-compose.yml     # Orquestación de contenedores (Fase 2)
├── init_db.py             # Inicialización y seed de la base de datos
└── requirements.txt
```

---

## Cómo correrlo localmente

**Prerrequisitos:** [Ollama](https://ollama.com) instalado + Python 3.11+

```bash
# 1. Clonar e instalar
git clone https://github.com/Gusmal02/pharma-agent-stack.git
cd pharma-agent-stack
python -m venv venv && source venv/Scripts/activate
pip install -r requirements.txt

# 2. Descargar el modelo
ollama pull qwen2.5-coder:7b-instruct-q4_K_M

# 3. Configurar entorno
echo "OLLAMA_BASE_URL=http://localhost:11434" > .env
echo "MODEL_NAME=qwen2.5-coder:7b-instruct-q4_K_M" >> .env

# 4. Inicializar base de datos
python init_db.py

# 5. Levantar la API
uvicorn app.main_api:app --host 127.0.0.1 --port 8085 --reload
```

---

## Hoja de ruta de escalabilidad

Este proyecto está diseñado bajo principios de arquitectura modular para expandirse en fases:

**Fase 2 — RAG semántico vectorial:** Migrar el motor de búsqueda a ChromaDB con embeddings locales (`nomic-embed-text` vía Ollama) para soportar consultas con sinónimos y tolerancia a errores ortográficos.

**Fase 3 — Contenedorización segura (DevSecOps):** Dockerfiles multi-stage con imágenes `python:3.11-slim-bookworm` y ejecución bajo usuario no-root (`appuser`). Ollama en contenedor aislado con red interna en `docker-compose`. Manifiestos de Kubernetes con `StatefulSet` para el motor de inferencia y `HorizontalPodAutoscaler` para la API.

**Fase 4 — Automatización de flujos (n8n):** Integrar la API REST con n8n para alertas automáticas de stock crítico, confirmaciones de recetas validadas por Telegram y auditoría de transacciones en sistemas ERP externos.

---

## El mismo esqueleto, otros dominios

La arquitectura es un patrón desacoplado. El mismo núcleo — FastAPI + Agente con memoria + Tools + Base de datos — puede adaptarse a otros sectores cambiando únicamente los modelos de datos y las herramientas:

**Legal y Cumplimiento (LegalTech):** Reemplazar el inventario por un repositorio de contratos, el RAG por jurisprudencia y leyes locales, y la validación de recetas por un validador de firmas o cláusulas de riesgo.

**Soporte Técnico de IT (SecOps):** Cambiar los medicamentos por inventario de hardware o activos de red, el manual por playbooks de mitigación de incidentes, y las herramientas para consultar logs en vivo o bases de datos de vulnerabilidades (CVEs).

**Logística y Cadena de Suministro (Supply Chain):** Adaptar las tablas para tracking de envíos, guías de transporte y manuales de operaciones aduaneras o de almacenamiento especializado.

---

## Sobre este proyecto

Lo construí para demostrar que puedo diseñar e implementar sistemas de IA aplicados a problemas reales de negocio — no solo correr notebooks. El sector farmacéutico fue una elección deliberada: es un dominio donde los errores tienen consecuencias reales, lo que obliga a pensar en validación, seguridad y robustez desde el inicio.

*Gustavo Maldonado 