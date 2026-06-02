# app/tools.py
import os
from pathlib import Path
from langchain_core.tools import tool
from app.database import SessionLocal
from app.models.pharma import Medicamento, RecetaDigital
from app.rag_utils import buscar_en_vademecum

BASE_DIR = Path(__file__).resolve().parent
# BASE_DIR = .../pharma-agent-stack/app/
# La carpeta knowledge está DENTRO de app/, no en la raíz del proyecto
RUTA_INSULINA = BASE_DIR / "knowledge" / "insulina.md"


@tool
def verificar_stock(nombre_medicamento: str) -> str:
    """
    Busca un medicamento en el inventario de la farmacia para conocer su precio,
    stock disponible y si requiere receta médica para su venta.
    Usa esta herramienta cuando el usuario pregunte si hay un medicamento disponible o su costo.
    """
    db = SessionLocal()
    try:
        medicamento = (
            db.query(Medicamento)
            .filter(Medicamento.nombre.ilike(f"%{nombre_medicamento}%"))
            .first()
        )
        if not medicamento:
            return f"No se encontró ningún medicamento que coincida con '{nombre_medicamento}' en el catálogo."

        req_receta = getattr(medicamento, "requiere_receta", False)
        estado_receta = (
            "SÍ requiere receta médica estricta"
            if req_receta
            else "Es de venta libre (No requiere receta)"
        )
        return (
            f"Resultados para '{medicamento.nombre}':\n"
            f"- Stock disponible: {medicamento.stock} unidades\n"
            f"- Precio unitario: ${medicamento.precio:.2f} MXN\n"
            f"- Requisito: {estado_receta}.\n"
        )
    except Exception as e:
        return f"Error al consultar el inventario: {str(e)}"
    finally:
        db.close()


@tool
def validar_receta_medica(codigo_receta: str, nombre_medicamento_solicitado: str) -> str:
    """
    Verifica si un código o folio de receta digital es válido en el sistema de la farmacia
    y comprueba si autoriza el medicamento específico que el usuario intenta comprar.
    """
    db = SessionLocal()
    try:
        receta = (
            db.query(RecetaDigital)
            .filter(RecetaDigital.codigo_receta == codigo_receta.strip())
            .first()
        )
        if not receta:
            return f"RECHAZADO: La receta con código '{codigo_receta}' NO es válida o no existe en nuestro sistema."

        nom_autorizado = receta.medicamento.nombre.lower()
        nom_solicitado = nombre_medicamento_solicitado.lower()

        if nom_solicitado not in nom_autorizado and nom_autorizado not in nom_solicitado:
            return (
                f"OPERACIÓN RECHAZADA POR SEGURIDAD:\n"
                f"- El folio '{codigo_receta}' es válido y pertenece al paciente {receta.paciente}.\n"
                f"- Esta receta AUTORIZA EXCLUSIVAMENTE: {receta.medicamento.nombre}.\n"
                f"- El usuario intenta utilizarla para adquirir: {nombre_medicamento_solicitado}.\n"
                f"- ACCIÓN: Niega la venta de {nombre_medicamento_solicitado} con esta receta."
            )
        return (
            f"¡Receta Digital VALIDADA con éxito!\n"
            f"- Código Folio: {receta.codigo_receta}\n"
            f"- Médico Emisor: {receta.medico}\n"
            f"- Paciente: {receta.paciente}\n"
            f"- Medicamento Autorizado: {receta.medicamento.nombre}\n"
            f"- El medicamento coincide con lo solicitado.\n"
        )
    except Exception as e:
        return f"Error al validar la receta: {str(e)}"
    finally:
        db.close()


@tool
def consultar_manual_conocimiento(tema: str) -> str:
    """
    Busca información médica detallada, guías de uso, almacenamiento o
    contraindicaciones de un medicamento en los manuales de conocimiento (RAG).
    Usa esta herramienta cuando el usuario pregunte por almacenamiento, temperatura,
    dosis, contraindicaciones o instrucciones del manual.
    """
    if not RUTA_INSULINA.exists():
        return (
            f"Error: Manual no encontrado en '{RUTA_INSULINA}'. "
            f"Verifica que el archivo exista en app/knowledge/insulina.md"
        )

    return buscar_en_vademecum(str(RUTA_INSULINA), tema)


tools_catálogo = [verificar_stock, validar_receta_medica, consultar_manual_conocimiento]