# TECNICO.md — Documentación Técnica

Decisiones de arquitectura, patrones de diseño y problemas resueltos durante el desarrollo de Pharma-Agent-Stack.

---

## 1. Por qué LangGraph sobre LangChain básico

LangChain básico implementa un flujo lineal: el LLM recibe input → decide herramienta → ejecuta → responde. No hay estado explícito entre pasos ni control de flujo condicional.

LangGraph modela el agente como un grafo dirigido con estado tipado (`AgentState`). Cada nodo es una función pura que recibe el estado completo y devuelve el estado modificado. El router `decidir_ruta` evalúa condicionalmente qué nodo ejecutar a continuación.

**Ventajas concretas en este proyecto:**

- El estado `tool_name`, `tool_args`, `tool_result` y `output` fluye explícitamente entre nodos. No hay variables ocultas ni efectos laterales.
- El nodo `nodo_sintetizar` recibe `tool_result` y `tool_args` completos, lo que permite al blindaje anti-JSON recuperar el contexto original si el LLM falla.
- La arquitectura escala naturalmente a flujos multi-agente: se pueden agregar nodos de verificación, escalamiento o auditoría sin modificar los nodos existentes.

**Fallback:** Si LangGraph no está instalado, el sistema cae automáticamente al ejecutor original basado en LangChain. Esta decisión garantiza que el proyecto funcione en entornos donde la dependencia no esté disponible.

---

## 2. Patrón de fallback automático (LLM y RAG)

Tanto el LLM como el motor RAG implementan el mismo patrón de fallback en tres capas:

```
Intento 1: GCP (Gemini / Vertex AI)
    ↓ falla o no hay credenciales
Intento 2: Local (Ollama / RAG sobre Markdown)
    ↓ falla
Intento 3: Respuesta de error controlada
```

**Implementación en `_inicializar_llm()`:**

La función verifica la presencia de `GOOGLE_API_KEY` o `GCP_PROJECT_ID` en el entorno. Si alguna existe, intenta instanciar `ChatGoogleGenerativeAI`. Si la importación o la instanciación falla por cualquier motivo, el `except` captura la excepción y cae a `ChatOllama`. El modo activo se determina en tiempo de inicialización, no en cada llamada, para evitar overhead.

**Implementación en `buscar_en_vademecum()`:**

La función evalúa cuatro condiciones antes de intentar Vertex AI: SDK instalado, `indice_id` presente, `endpoint_id` presente, y `_inicializar_vertexai()` exitoso. Si cualquiera falla, el RAG local se activa sin lanzar excepción al caller.

**Por qué este diseño:**

En entornos con datos sensibles (salud, legal, finanzas), la disponibilidad del servicio es crítica. Un agente que falla completamente cuando GCP no está disponible es inaceptable en producción. El fallback garantiza continuidad de servicio con degradación controlada.

---

## 3. Mecanismo de fallback por palabras clave

Los modelos cuantizados a 4 bits (q4_K_M) no siempre emiten `tool_calls` estructurados. En lugar de depender exclusivamente del formato nativo del LLM, el sistema implementa tres capas de detección de intención:

**Capa 1 — tool_calls nativo:** El LLM emite el objeto estructurado estándar de LangChain. Es el camino ideal.

**Capa 2 — JSON embebido:** El LLM responde con texto plano que contiene JSON con `name` y `arguments`. Se extrae con regex y se parsea.

**Capa 3 — Keywords:** Si las capas 1 y 2 fallan, se cruzan las palabras del input contra un diccionario de intenciones. Cada intención mapea a una herramienta con sus argumentos extraídos del texto.

**Problema resuelto con `validar_receta_medica`:**

La herramienta requiere dos argumentos: `codigo_receta` y `nombre_medicamento_solicitado`. El regex `rec-[\w-]+` extrae el folio directamente del texto del usuario. Sin este mecanismo, el agente devolvía el JSON crudo al cliente en lugar de ejecutar la herramienta.

---

## 4. Blindaje anti-JSON en síntesis

**El problema:** Los LLMs cuantizados, especialmente bajo carga, pueden devolver JSON estructurado en lugar de texto conversacional incluso cuando el prompt lo prohíbe explícitamente. Esto ocurre porque el modelo fue entrenado con datos donde la respuesta correcta era JSON.

**La solución en `_sintetizar_resultado()`:**

La función `_es_json_crudo()` evalúa si la respuesta completa del LLM es JSON válido (empieza con `{` o `[` y parsea sin error). Si lo es, se construye la respuesta directamente en Python usando los datos del estado:

- Si `tool_result` contiene "rechazado" o "no coincide" → respuesta de rechazo empática con los datos del folio
- Cualquier otro caso → resumen del resultado como texto plano

**Por qué función centralizada:**

La lógica de síntesis y blindaje era duplicada entre LangGraph y el fallback de LangChain. Al extraerla a `_sintetizar_resultado()`, ambos ejecutores comparten el mismo comportamiento garantizado.

---

## 5. Gestión de conexiones SQLAlchemy

**El problema original:** Las sesiones de SQLAlchemy quedaban abiertas cuando ocurría una excepción dentro de una herramienta. Cada llamada al agente abría una sesión nueva. Con el tiempo, el pool de conexiones se agotaba silenciosamente sin lanzar error visible.

**La solución:** Todas las herramientas en `tools.py` usan el patrón `try/finally`:

```python
db = SessionLocal()
try:
    # operaciones
    return resultado
except Exception as e:
    return f"Error: {str(e)}"
finally:
    db.close()  # Se ejecuta siempre, incluso si hay excepción
```

El `finally` garantiza que `db.close()` se ejecute en cualquier ruta de ejecución, incluyendo excepciones no anticipadas.

---

## 6. Resolución de rutas en producción

**El problema:** La ruta `knowledge/insulina.md` era relativa al directorio de trabajo (`cwd`). Cuando uvicorn se lanza desde la raíz del proyecto, `cwd` es la raíz y la ruta resuelve correctamente. Cuando se lanza desde otro directorio o dentro de Docker, `cwd` cambia y la ruta falla con `FileNotFoundError`.

**La solución:**

```python
BASE_DIR = Path(__file__).resolve().parent
RUTA_INSULINA = BASE_DIR / "knowledge" / "insulina.md"
```

`Path(__file__).resolve()` devuelve la ruta absoluta del archivo fuente (`tools.py`), independientemente de desde dónde se ejecute el proceso. `.parent` sube un nivel al directorio `app/`. Esta ruta es estable en cualquier entorno.

---

## 7. Dockerfile multi-stage y usuario no-root

**Por qué multi-stage:**

La imagen de construcción (`builder`) necesita `build-essential` para compilar dependencias con extensiones C (numpy, pandas). La imagen de runtime (`runtime`) no necesita estas herramientas. Al copiar solo los artefactos compilados con `COPY --from=builder /install /usr/local`, la imagen final es más pequeña y no expone herramientas de compilación que podrían usarse para escalar privilegios.

**Por qué usuario no-root:**

El principio de menor privilegio (NIST AC-6) establece que los procesos deben ejecutarse con los permisos mínimos necesarios. Un contenedor ejecutado como `root` que sea comprometido da al atacante control total del host si hay escape del contenedor. `appuser` no tiene shell, no tiene directorio home y no puede escalar privilegios.

```dockerfile
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup --no-create-home appuser
USER appuser
```

---

## 8. Variables de entorno y Secret Manager

**En desarrollo local:** Las variables sensibles van en `.env` (excluido de git via `.gitignore`). El patrón `os.getenv("KEY", "default")` garantiza que el sistema funcione aunque la variable no esté definida.

**En Cloud Run:** Las API keys nunca van en texto plano en el YAML de despliegue. Se almacenan en GCP Secret Manager y se inyectan en el contenedor como variables de entorno en tiempo de ejecución:

```yaml
- name: GOOGLE_API_KEY
  valueFrom:
    secretKeyRef:
      name: google-api-key
      key: latest
```

Esto garantiza que las credenciales nunca aparezcan en logs, en el historial de git, ni en la definición de la infraestructura.

---

## 9. Cache TTL en analytics

Las funciones de análisis (`analizar_tendencia`, `calcular_velocidad_consumo`, `evaluar_riesgo_desabasto`) usan `@cached(TTLCache(maxsize=32, ttl=300))`.

**Por qué:** Cada llamada al agente puede invocar múltiples funciones de análisis para el mismo medicamento dentro de la misma sesión. Sin cache, cada llamada ejecuta una query SQL + regresión lineal sobre 365 días de datos. Con TTL de 5 minutos, las llamadas subsecuentes para el mismo `medicamento_id` devuelven el resultado en memoria sin tocar la base de datos.

**Por qué TTL y no cache permanente:** Los datos de stock y ventas cambian. Un cache sin expiración devolvería datos obsoletos. 5 minutos es un equilibrio entre performance y frescura de datos para un entorno farmacéutico.

---

## 10. Decisión: LightGBM sobre XGBoost (proyecto de fraude relacionado)

Documentada aquí como referencia de criterio arquitectónico aplicado consistentemente:

- LightGBM maneja valores nulos nativamente sin imputación previa. En datasets financieros los nulos son informativos (transacción sin campo = comportamiento anómalo), no errores.
- LightGBM usa histogram-based learning que reduce la complejidad de O(n) a O(bins) en la construcción de árboles. En datasets de +590,000 registros, la diferencia de velocidad es medible.
- XGBoost requiere imputación explícita y es más lento en datasets grandes sin GPU.

El mismo criterio de investigación previa a la decisión se aplica en cada componente de este proyecto.

---

*Gustavo Maldonado — [github.com/Gusmal02](https://github.com/Gusmal02)*