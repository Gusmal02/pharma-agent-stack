# Pharma-Agent-Stack

**Sistema agéntico con RAG empresarial para automatización de pedidos farmacéuticos**  
LangGraph · Gemini API · Vertex AI Vector Search · FastAPI · Docker · GCP

> **Estado:** Fase 2 activa — Migración a LangGraph + GCP (Gemini + Vertex AI) con fallback local on-premise.

---

## ¿Qué problema resuelve?

Las farmacias y distribuidoras del sector salud manejan medicamentos controlados, recetas digitales y manuales técnicos de almacenamiento. Automatizar ese flujo con IA es complejo porque **los datos son sensibles y no pueden salir de la infraestructura interna**.

Este proyecto resuelve ese problema con una arquitectura de dos modos:

- **On-premise:** LLM local (Ollama + Qwen2.5-Coder) sin dependencias de nube. Para entornos con datos sensibles.
- **Cloud (GCP):** Gemini API como LLM + Vertex AI Vector Search para RAG semántico empresarial. Para escala y consultas con sinónimos y tolerancia a errores.

El sistema detecta automáticamente qué modo usar según las variables de entorno disponibles.

---

## Demo rápido

**Consulta del manual técnico (RAG):**
```bash
curl -X POST http://127.0.0.1:8080/chat \
     -H "Content-Type: application/json" \
     -d '{"input": "A qué temperatura debo guardar la insulina?", "chat_history": []}'
```
```json
{
  "output": "La insulina sin abrir debe conservarse entre 2°C y 8°C en refrigeración. Una vez abierta, puede mantenerse a temperatura ambiente entre 15°C y 30°C por un máximo de 28 días."
}
```

**Intento de uso fraudulento de receta:**
```bash
curl -X POST http://127.0.0.1:8080/chat \
     -H "Content-Type: application/json" \
     -d '{"input": "Quiero comprar Insulina con la receta REC-9988-77", "chat_history": []}'
```
```json
{
  "output": "Lo siento, no puedo autorizar la venta de insulina. El folio REC-9988-77 es válido pero autoriza exclusivamente Amoxicilina 500mg para el paciente Carlos López Mendoza. Por favor verifica tus datos o consulta con tu médico."
}
```

---

## Stack tecnológico

| Capa | On-premise | GCP (Cloud) |
|---|---|---|
| **LLM** | Ollama + Qwen2.5-Coder 7B | Gemini API (gemini-1.5-flash) |
| **Orquestación** | LangGraph + LangChain | LangGraph + LangChain |
| **RAG** | Motor propio sobre Markdown | Vertex AI Vector Search |
| **Embeddings** | — | text-embedding-004 |
| **API** | FastAPI + Uvicorn + Pydantic v2 | FastAPI + Uvicorn + Pydantic v2 |
| **Base de datos** | SQLite + SQLAlchemy 2.0 | SQLite + SQLAlchemy 2.0 |
| **Despliegue** | Docker multi-stage, usuario no-root | Cloud Run + Secret Manager |
| **CI/CD** | GitHub Actions + Bandit (SAST) | GitHub Actions + Bandit (SAST) |

---

## Arquitectura del grafo (LangGraph)

```
Consulta del usuario
        │
        ▼
  [nodo_clasificar]
  LLM decide herramienta
  (tool_call → fallback keywords)
        │
   ┌────┴────┐
   ▼         ▼
[ejecutar  [respuesta
  _tool]    _directa]
   │
   ▼
[nodo_sintetizar]
LLM convierte resultado
en respuesta conversacional
        │
        ▼
     Respuesta
```

El router `decidir_ruta` evalúa si se detectó una herramienta. Si sí, ejecuta y sintetiza. Si no, responde directamente. Cada nodo es una función pura con estado explícito — sin efectos laterales entre pasos.

---

## Herramientas del agente

| Herramienta | Función |
|---|---|
| `verificar_stock` | Consulta precio, disponibilidad y requisito de receta |
| `validar_receta_medica` | Verifica folio y valida que el medicamento coincida |
| `consultar_manual_conocimiento` | RAG sobre manuales técnicos (Markdown → Vertex AI) |
| `predecir_demanda_futura` | Regresión lineal sobre ventas de los últimos 90 días |
| `verificar_riesgo_desabasto` | Cruza velocidad de consumo con stock actual |

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
cp .env.example .env
# Edita .env con tus valores

# 4. Inicializar base de datos
python init_db.py

# 5. Levantar la API
uvicorn app.main_api:app --host 0.0.0.0 --port 8080 --reload
```

**Con Docker (modo local):**
```bash
docker compose up
```

**Con Docker (modo GCP):**
```bash
docker compose --profile gcp up
```

---

## Variables de entorno

```bash
# Ollama (modo local)
OLLAMA_BASE_URL=http://localhost:11434
MODEL_NAME=qwen2.5-coder:7b-instruct-q4_K_M

# GCP (modo cloud — dejar vacío para usar Ollama)
GCP_PROJECT_ID=
GCP_REGION=us-central1
GEMINI_MODEL=gemini-1.5-flash
GOOGLE_API_KEY=
VERTEX_INDEX_ID=
VERTEX_ENDPOINT_ID=
```

El sistema detecta automáticamente el modo según las variables disponibles. Si `GCP_PROJECT_ID` y `GOOGLE_API_KEY` están vacíos, usa Ollama local.

---

## Hoja de ruta

**Fase 1 ✅** — Core Agent + RAG local + API REST + SQLite  
**Fase 2 🔄** — LangGraph + Gemini API + Vertex AI Vector Search + Cloud Run  
**Fase 3 ⏳** — n8n para orquestación de procesos empresariales (alertas, notificaciones, ERP)  
**Fase 4 ⏳** — Kubernetes con StatefulSet + HorizontalPodAutoscaler  

---

## El mismo esqueleto, otros dominios

La arquitectura es un patrón desacoplado. El núcleo — FastAPI + LangGraph + Tools + RAG — es adaptable cambiando únicamente los modelos de datos y las herramientas:

- **LegalTech:** Contratos → RAG sobre jurisprudencia → validador de cláusulas de riesgo
- **SecOps:** Activos de red → RAG sobre playbooks de incidentes → clasificador de severidad
- **Supply Chain:** Envíos → RAG sobre manuales aduaneros → predictor de desabasto

---

*Gustavo Maldonado — [github.com/Gusmal02](https://github.com/Gusmal02)*