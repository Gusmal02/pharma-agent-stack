# app/rag_utils.py
import re
import os
import logging

logger = logging.getLogger(__name__)

# ── Intento de importar dependencias de GCP ──────────────────────────────────
try:
    from google.cloud import aiplatform
    from vertexai.language_models import TextEmbeddingModel
    import vertexai
    GCP_DISPONIBLE = True
except ImportError:
    GCP_DISPONIBLE = False
    logger.warning("SDK de GCP no instalado. Usando RAG local como fallback.")


# ── Motor Vertex AI Vector Search ────────────────────────────────────────────
def _inicializar_vertexai() -> bool:
    """Inicializa Vertex AI con las credenciales del entorno."""
    proyecto = os.getenv("GCP_PROJECT_ID")
    region = os.getenv("GCP_REGION", "us-central1")

    if not proyecto:
        logger.warning("GCP_PROJECT_ID no configurado. Usando RAG local.")
        return False

    try:
        vertexai.init(project=proyecto, location=region)
        return True
    except Exception as e:
        logger.error(f"Error inicializando Vertex AI: {e}")
        return False


def _buscar_vertexai(termino: str, indice_id: str, endpoint_id: str) -> str:
    """
    Búsqueda semántica usando Vertex AI Vector Search.
    Genera embedding del término y recupera los fragmentos más similares.
    """
    try:
        # Generar embedding del término de búsqueda
        modelo_embedding = TextEmbeddingModel.from_pretrained("text-embedding-004")
        embeddings = modelo_embedding.get_embeddings([termino])
        vector_consulta = embeddings[0].values

        # Consultar el índice de Vertex AI
        cliente_index = aiplatform.MatchingEngineIndexEndpoint(
            index_endpoint_name=endpoint_id
        )
        respuesta = cliente_index.find_neighbors(
            deployed_index_id=indice_id,
            queries=[vector_consulta],
            num_neighbors=3
        )

        if not respuesta or not respuesta[0]:
            return f"No se encontró información sobre '{termino}' en la base de conocimiento."

        # Recuperar los fragmentos por ID
        fragmentos = []
        for vecino in respuesta[0]:
            fragmentos.append(f"[Relevancia: {vecino.distance:.2f}]\n{vecino.id}")

        contexto = "\n\n---\n\n".join(fragmentos)
        return f"[INFORMACIÓN RECUPERADA — Vertex AI Vector Search]:\n{contexto}"

    except Exception as e:
        logger.error(f"Error en Vertex AI Vector Search: {e}")
        raise


# ── Motor RAG Local (fallback) ───────────────────────────────────────────────
def _buscar_local(ruta_archivo: str, termino: str) -> str:
    """
    RAG local original: segmenta Markdown por secciones y recupera
    fragmentos relevantes cruzando palabras clave.
    """
    try:
        with open(ruta_archivo, "r", encoding="utf-8") as f:
            contenido = f.read()

        primer_encabezado = re.search(r"\n## ", contenido)
        if primer_encabezado:
            bloque_inicial = contenido[: primer_encabezado.start()].strip()
            resto = contenido[primer_encabezado.start():]
            secciones_marcadas = re.split(r"(?=\n## )", resto)
            secciones = (
                [bloque_inicial] + secciones_marcadas
                if bloque_inicial
                else secciones_marcadas
            )
        else:
            secciones = [contenido]

        palabras_clave = [p.lower() for p in termino.split() if len(p) > 2]
        if not palabras_clave:
            palabras_clave = [termino.lower()]

        fragmentos_encontrados = []
        for seccion in secciones:
            if any(palabra in seccion.lower() for palabra in palabras_clave):
                fragmentos_encontrados.append(seccion.strip())

        if fragmentos_encontrados:
            contexto = "\n\n---\n\n".join(fragmentos_encontrados)
            return f"[INFORMACIÓN RECUPERADA — RAG Local]:\n{contexto}"

        return (
            f"No se encontró información específica sobre '{termino}' "
            "en el manual de conocimiento."
        )

    except FileNotFoundError:
        return f"Error: El archivo '{ruta_archivo}' no existe. Verifica la ruta."
    except Exception as e:
        return f"Error en RAG local: {str(e)}"


# ── Función principal con fallback automático ────────────────────────────────
def buscar_en_vademecum(
    ruta_archivo: str,
    termino_busqueda: str,
    indice_id: str = None,
    endpoint_id: str = None
) -> str:
    """
    Motor RAG con fallback automático:
    1. Intenta Vertex AI Vector Search si GCP está configurado
    2. Cae a RAG local si GCP no está disponible o falla

    Args:
        ruta_archivo: Ruta al archivo Markdown para RAG local
        termino_busqueda: Consulta del usuario
        indice_id: ID del índice desplegado en Vertex AI (opcional)
        endpoint_id: ID del endpoint de Vertex AI (opcional)
    """
    usar_vertexai = (
        GCP_DISPONIBLE
        and indice_id
        and endpoint_id
        and _inicializar_vertexai()
    )

    if usar_vertexai:
        try:
            logger.info("Usando Vertex AI Vector Search.")
            return _buscar_vertexai(termino_busqueda, indice_id, endpoint_id)
        except Exception as e:
            logger.warning(f"Vertex AI falló: {e}. Activando RAG local.")

    logger.info("Usando RAG local.")
    return _buscar_local(ruta_archivo, termino_busqueda)