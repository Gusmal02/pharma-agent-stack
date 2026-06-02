# app/tools.py
import os
from pathlib import Path
from langchain_core.tools import tool
from app.database import SessionLocal
from app.models.pharma import Medicamento, RecetaDigital
from app.rag_utils import buscar_en_vademecum
from app.analytics import (
    analizar_tendencia,
    calcular_velocidad_consumo,
    evaluar_riesgo_desabasto,
    resolver_medicamento_id,
)

BASE_DIR = Path(__file__).resolve().parent
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


@tool
def predecir_demanda_futura(nombre_medicamento: str) -> str:
    """
    Analiza la tendencia de ventas recientes de un medicamento usando regresión lineal
    y proyecta si la demanda subirá, bajará o se mantendrá estable.
    Usa esta herramienta cuando el usuario pregunte por proyecciones, tendencias
    o comportamiento futuro de ventas de un medicamento.
    """
    med_id = resolver_medicamento_id(nombre_medicamento)
    if not med_id:
        return f"No se encontró el medicamento '{nombre_medicamento}' en el sistema."

    resultado = analizar_tendencia(med_id)

    if "error" in resultado:
        return f"No se pudo analizar la tendencia: {resultado['error']}"

    velocidad = calcular_velocidad_consumo(med_id)
    proyeccion = velocidad.get("proyeccion_unidades_30d", "N/D")
    revenue_30d = velocidad.get("revenue_proyectado_30d", "N/D")

    return (
        f"Análisis de tendencia — {resultado['medicamento']}:\n"
        f"- Periodo analizado: {resultado['periodo_analizado']}\n"
        f"- Promedio diario actual: {resultado['promedio_diario']} unidades/día\n"
        f"- Dirección de la tendencia: {resultado['direccion'].upper()}\n"
        f"- Coeficiente (cambio diario): {resultado['coeficiente_tendencia']} uds/día\n"
        f"- Confiabilidad del modelo (R²): {resultado['r2']} "
        f"({'confiable' if resultado['r2'] >= 0.4 else 'baja confiabilidad'})\n"
        f"- Proyección próximos 30 días: ~{proyeccion} unidades\n"
        f"- Revenue proyectado 30 días: ${revenue_30d} MXN\n"
        f"\nInterpretación: {resultado['interpretacion']}"
    )


@tool
def verificar_riesgo_desabasto(nombre_medicamento: str) -> str:
    """
    Evalúa el riesgo de quedarse sin stock de un medicamento cruzando
    la velocidad de consumo actual con el inventario disponible.
    Usa esta herramienta cuando el usuario pregunte sobre abastecimiento,
    cuándo se acaba un medicamento, si hay riesgo de desabasto o cuándo comprar.
    """
    med_id = resolver_medicamento_id(nombre_medicamento)
    if not med_id:
        return f"No se encontró el medicamento '{nombre_medicamento}' en el sistema."

    resultado = evaluar_riesgo_desabasto(med_id)

    if "error" in resultado:
        return f"No se pudo evaluar el riesgo: {resultado['error']}"

    velocidad = calcular_velocidad_consumo(med_id)
    revenue_dia = velocidad.get("revenue_diario_promedio", "N/D")

    return (
        f"Evaluación de riesgo de desabasto — {resultado['medicamento']}:\n"
        f"- Stock actual: {resultado['stock_actual']} unidades\n"
        f"- Velocidad de consumo: {resultado['unidades_por_dia']} unidades/día\n"
        f"- Revenue diario promedio: ${revenue_dia} MXN\n"
        f"- Días hasta agotamiento: {resultado['dias_hasta_agotamiento']} días\n"
        f"- Nivel de riesgo: {resultado['nivel_riesgo']}\n"
        f"\nRecomendación: {resultado['recomendacion']}"
    )


tools_catálogo = [
    verificar_stock,
    validar_receta_medica,
    consultar_manual_conocimiento,
    predecir_demanda_futura,
    verificar_riesgo_desabasto,
]