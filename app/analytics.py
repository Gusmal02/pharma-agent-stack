# app/analytics.py
import pandas as pd
import numpy as np
from datetime import date, timedelta
from sklearn.linear_model import LinearRegression
from cachetools import cached, TTLCache
from app.database import SessionLocal
from app.models.pharma import VentaHistorica, Medicamento

# Cache de 5 minutos — evita recalcular en cada llamada del agente
_cache = TTLCache(maxsize=32, ttl=300)


def _cargar_ventas_dataframe(medicamento_id: int) -> tuple[pd.DataFrame, str]:
    """
    Carga el historial de ventas de un medicamento desde SQLite
    y lo devuelve como DataFrame junto con el nombre del medicamento.
    """
    db = SessionLocal()
    try:
        med = db.query(Medicamento).filter(Medicamento.id == medicamento_id).first()
        if not med:
            return pd.DataFrame(), ""

        ventas = (
            db.query(VentaHistorica)
            .filter(VentaHistorica.medicamento_id == medicamento_id)
            .all()
        )

        if not ventas:
            return pd.DataFrame(), med.nombre

        df = pd.DataFrame([{
            "fecha": v.fecha,
            "unidades": v.unidades_vendidas,
            "precio": v.precio_unitario_en_venta,
            "revenue": v.unidades_vendidas * v.precio_unitario_en_venta,
        } for v in ventas])

        df["fecha"] = pd.to_datetime(df["fecha"])
        df = df.sort_values("fecha").reset_index(drop=True)
        return df, med.nombre

    finally:
        db.close()


def _buscar_medicamento_por_nombre(nombre: str) -> int | None:
    """Busca el ID de un medicamento por nombre (búsqueda parcial, case-insensitive)."""
    db = SessionLocal()
    try:
        med = (
            db.query(Medicamento)
            .filter(Medicamento.nombre.ilike(f"%{nombre}%"))
            .first()
        )
        return med.id if med else None
    finally:
        db.close()


@cached(_cache)
def analizar_tendencia(medicamento_id: int) -> dict:
    """
    Aplica regresión lineal sobre las ventas diarias de los últimos 90 días.
    Devuelve la dirección de la tendencia, el coeficiente, R² y confiabilidad.

    Se usan solo 90 días (no los 365 completos) para capturar la tendencia
    reciente en lugar de promediar sobre estacionalidad anual completa.
    """
    df, nombre = _cargar_ventas_dataframe(medicamento_id)

    if df.empty:
        return {"error": f"Sin datos para medicamento ID {medicamento_id}"}

    # Filtrar últimos 90 días
    corte = pd.Timestamp(date.today() - timedelta(days=90))
    df_reciente = df[df["fecha"] >= corte].copy()

    if len(df_reciente) < 14:
        return {"error": "Datos insuficientes (menos de 14 días) para calcular tendencia."}

    # Variable independiente: día ordinal (número de día desde el inicio del periodo)
    df_reciente["dia_num"] = (
        df_reciente["fecha"] - df_reciente["fecha"].min()
    ).dt.days.values

    X = df_reciente["dia_num"].values.reshape(-1, 1)
    y = df_reciente["unidades"].values

    modelo = LinearRegression()
    modelo.fit(X, y)

    coef = round(modelo.coef_[0], 4)       # unidades extra por día
    r2 = round(modelo.score(X, y), 4)      # calidad del ajuste (0-1)
    promedio = round(float(np.mean(y)), 2)

    # Clasificar dirección con umbral mínimo para evitar falsos positivos
    if r2 < 0.4:
        direccion = "no concluyente"
        interpretacion = (
            f"La demanda de {nombre} no muestra una tendencia clara en los últimos "
            f"90 días (R²={r2}, muy baja correlación). Los datos son variables."
        )
    elif coef > 0.05:
        direccion = "al alza"
        interpretacion = (
            f"La demanda de {nombre} está creciendo aproximadamente "
            f"{abs(coef):.2f} unidades adicionales por día."
        )
    elif coef < -0.05:
        direccion = "a la baja"
        interpretacion = (
            f"La demanda de {nombre} está disminuyendo aproximadamente "
            f"{abs(coef):.2f} unidades por día."
        )
    else:
        direccion = "estable"
        interpretacion = (
            f"La demanda de {nombre} se mantiene estable con un promedio "
            f"de {promedio} unidades diarias."
        )

    return {
        "medicamento": nombre,
        "medicamento_id": medicamento_id,
        "periodo_analizado": "últimos 90 días",
        "promedio_diario": promedio,
        "coeficiente_tendencia": coef,
        "r2": r2,
        "direccion": direccion,
        "interpretacion": interpretacion,
    }


@cached(_cache)
def calcular_velocidad_consumo(medicamento_id: int) -> dict:
    """
    Calcula la velocidad de consumo promedio usando los últimos 30 días.
    Devuelve unidades/día, revenue diario promedio y proyección a 30 días.
    """
    df, nombre = _cargar_ventas_dataframe(medicamento_id)

    if df.empty:
        return {"error": f"Sin datos para medicamento ID {medicamento_id}"}

    corte = pd.Timestamp(date.today() - timedelta(days=30))
    df_reciente = df[df["fecha"] >= corte].copy()

    if df_reciente.empty:
        return {"error": "Sin ventas en los últimos 30 días."}

    unidades_dia = round(float(df_reciente["unidades"].mean()), 2)
    revenue_dia = round(float(df_reciente["revenue"].mean()), 2)
    proyeccion_30d = round(unidades_dia * 30)
    revenue_proyectado_30d = round(revenue_dia * 30, 2)

    return {
        "medicamento": nombre,
        "medicamento_id": medicamento_id,
        "periodo_analizado": "últimos 30 días",
        "unidades_por_dia": units_dia if 'units_dia' in locals() else unidades_dia,
        "revenue_diario_promedio": revenue_dia,
        "proyeccion_unidades_30d": proyeccion_30d,
        "revenue_proyectado_30d": revenue_proyectado_30d,
    }


@cached(_cache)
def evaluar_riesgo_desabasto(medicamento_id: int) -> dict:
    """
    Cruza la velocidad de consumo actual con el stock disponible.
    Calcula en cuántos días se agotará el inventario y el nivel de riesgo.

    Umbrales de riesgo:
      CRÍTICO  → menos de 7 días de stock
      ALTO     → 7 a 14 días
      MEDIO    → 15 a 30 días
      BAJO     → más de 30 días
    """
    db = SessionLocal()
    try:
        med = db.query(Medicamento).filter(Medicamento.id == medicamento_id).first()
        if not med:
            return {"error": f"Medicamento ID {medicamento_id} no encontrado."}
        stock_actual = med.stock
        nombre = med.nombre
    finally:
        db.close()

    velocidad = calcular_velocidad_consumo(medicamento_id)
    if "error" in velocidad:
        return velocidad

    unidades_dia = velocidad["unidades_por_dia"]

    if unidades_dia <= 0:
        return {
            "medicamento": nombre,
            "stock_actual": stock_actual,
            "unidades_por_dia": 0,
            "dias_hasta_agotamiento": None,
            "nivel_riesgo": "SIN MOVIMIENTO",
            "recomendacion": f"{nombre} no registra ventas recientes. Verificar si sigue activo.",
        }

    dias_restantes = round(stock_actual / unidades_dia, 1)

    if dias_restantes < 7:
        nivel = "CRÍTICO"
        recomendacion = (
            f"ACCIÓN INMEDIATA: Con el ritmo actual ({unidades_dia} uds/día), "
            f"el stock de {nombre} se agotará en {dias_restantes} días. "
            f"Realizar orden de compra hoy."
        )
    elif dias_restantes < 14:
        nivel = "ALTO"
        recomendacion = (
            f"ATENCIÓN: Quedan aproximadamente {dias_restantes} días de stock. "
            f"Programar reabastecimiento esta semana."
        )
    elif dias_restantes < 30:
        nivel = "MEDIO"
        recomendacion = (
            f"Stock para {dias_restantes} días. "
            f"Planificar orden de compra en los próximos 7 días."
        )
    else:
        nivel = "BAJO"
        recomendacion = (
            f"Stock suficiente para {dias_restantes} días. "
            f"Sin acción inmediata requerida."
        )

    return {
        "medicamento": nombre,
        "stock_actual": stock_actual,
        "unidades_por_dia": unidades_dia,
        "dias_hasta_agotamiento": dias_restantes,
        "nivel_riesgo": nivel,
        "recomendacion": recomendacion,
    }


def resolver_medicamento_id(nombre_o_id: str) -> int | None:
    """
    Utilitario: acepta tanto un nombre ('insulina') como un ID ('6')
    y devuelve siempre el ID entero. Usado por las herramientas del agente.
    """
    if str(nombre_o_id).isdigit():
        return int(nombre_o_id)
    return _buscar_medicamento_por_nombre(nombre_o_id)
