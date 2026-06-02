# app/rag_utils.py
import re


def buscar_en_vademecum(ruta_archivo: str, termino_busqueda: str) -> str:
    """
    Motor RAG local: Lee, segmenta por secciones de Markdown y recupera
    el fragmento de conocimiento más relevante cruzando palabras clave.
    """
    try:
        with open(ruta_archivo, "r", encoding="utf-8") as f:
            contenido = f.read()

        # Separamos el bloque inicial (antes del primer ##) del resto.
        # re.split con lookahead descartaba este bloque en la versión anterior.
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
            # Documento sin secciones: se trata como un solo bloque
            secciones = [contenido]

        palabras_clave = [p.lower() for p in termino_busqueda.split() if len(p) > 2]
        if not palabras_clave:
            palabras_clave = [termino_busqueda.lower()]

        fragmentos_encontrados = []
        for seccion in secciones:
            seccion_bajo = seccion.lower()
            if any(palabra in seccion_bajo for palabra in palabras_clave):
                fragmentos_encontrados.append(seccion.strip())

        if fragmentos_encontrados:
            contexto_recuperado = "\n\n---\n\n".join(fragmentos_encontrados)
            return f"[INFORMACIÓN RECUPERADA DEL MANUAL TÉCNICO]:\n{contexto_recuperado}"

        return (
            f"No se encontró información específica sobre '{termino_busqueda}' "
            "en el manual de conocimiento."
        )

    except FileNotFoundError:
        return f"Error: El archivo '{ruta_archivo}' no existe. Verifica la ruta."
    except Exception as e:
        return f"Error al procesar el módulo RAG: {str(e)}"