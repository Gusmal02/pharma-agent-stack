# init_db.py
import sys
import os
import numpy as np
from datetime import date, timedelta

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, Base, SessionLocal
from app.models.pharma import Medicamento, RecetaDigital, VentaHistorica

print("=== INICIALIZANDO BASE DE DATOS LOCAL (SQLITE) ===")

print("Creando tablas en pharma.db...")
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

db = SessionLocal()

try:
    # ── 1. Catálogo de medicamentos ──────────────────────────────────────────
    print("Insertando catálogo de medicamentos...")

    medicamentos_iniciales = [
        Medicamento(
            nombre="Paracetamol 500mg",
            compuesto_activo="Paracetamol",
            precio=45.50,
            stock=150,
            requiere_receta=False,
        ),
        Medicamento(
            nombre="Ibuprofeno 400mg",
            compuesto_activo="Ibuprofeno",
            precio=62.00,
            stock=80,
            requiere_receta=False,
        ),
        Medicamento(
            nombre="Amoxicilina 500mg",
            compuesto_activo="Amoxicilina",
            precio=120.00,
            stock=35,
            requiere_receta=True,
        ),
        Medicamento(
            nombre="Clonazepam 2mg",
            compuesto_activo="Clonazepam",
            precio=210.00,
            stock=12,
            requiere_receta=True,
        ),
        Medicamento(
            nombre="Loratadina 10mg",
            compuesto_activo="Loratadina",
            precio=38.00,
            stock=200,
            requiere_receta=False,
        ),
        Medicamento(
            nombre="Insulina Glargina 100 UI/ml",
            compuesto_activo="Insulina",
            precio=480.00,
            stock=25,
            requiere_receta=True,
        ),
    ]

    db.add_all(medicamentos_iniciales)
    db.commit()

    # ── 2. Receta de prueba ──────────────────────────────────────────────────
    print("Insertando receta digital de prueba...")

    receta_prueba = RecetaDigital(
        codigo_receta="REC-9988-77",
        medico="Dr. Alejandro Cárdenas (Céd. 1234567)",
        paciente="Carlos López Mendoza",
        medicamento_id=3,  # Amoxicilina
    )

    db.add(receta_prueba)
    db.commit()

    # ── 3. Historial de ventas simulado (12 meses) ───────────────────────────
    print("Generando historial de ventas simulado (12 meses con estacionalidad)...")

    np.random.seed(42)  # Reproducibilidad: mismo seed = mismos datos siempre

    hoy = date.today()
    fecha_inicio = hoy - timedelta(days=365)

    # Perfil de cada medicamento:
    # base_diaria  → unidades promedio por día en temporada normal
    # pico_meses   → meses del año con demanda elevada (1=enero ... 12=diciembre)
    # factor_pico  → multiplicador de demanda en meses de pico
    # tendencia    → unidades extra que se suman cada mes (crecimiento lineal)
    # ruido_std    → desviación estándar del ruido gaussiano diario
    perfiles = {
        1: {  # Paracetamol — pico en invierno (nov-feb), tendencia leve al alza
            "base_diaria": 12,
            "pico_meses": [11, 12, 1, 2],
            "factor_pico": 2.2,
            "tendencia": 0.03,
            "ruido_std": 3,
        },
        2: {  # Ibuprofeno — pico en invierno, comportamiento similar al paracetamol
            "base_diaria": 8,
            "pico_meses": [11, 12, 1, 2],
            "factor_pico": 1.8,
            "tendencia": 0.01,
            "ruido_std": 2,
        },
        3: {  # Amoxicilina — pico en temporada de lluvia (jun-sep), demanda estable
            "base_diaria": 5,
            "pico_meses": [6, 7, 8, 9],
            "factor_pico": 1.6,
            "tendencia": 0.0,
            "ruido_std": 1.5,
        },
        4: {  # Clonazepam — demanda constante, sin estacionalidad marcada
            "base_diaria": 2,
            "pico_meses": [],
            "factor_pico": 1.0,
            "tendencia": 0.005,
            "ruido_std": 0.8,
        },
        5: {  # Loratadina — pico en primavera (mar-may) por alergias
            "base_diaria": 15,
            "pico_meses": [3, 4, 5],
            "factor_pico": 2.5,
            "tendencia": 0.02,
            "ruido_std": 4,
        },
        6: {  # Insulina — demanda estable y creciente (enfermedad crónica)
            "base_diaria": 3,
            "pico_meses": [],
            "factor_pico": 1.0,
            "tendencia": 0.04,  # Tendencia al alza más marcada
            "ruido_std": 0.5,
        },
    }

    ventas_a_insertar = []
    dias_transcurridos = (hoy - fecha_inicio).days

    for med_id, perfil in perfiles.items():
        # Precio del medicamento para registrar en la venta histórica
        med = db.query(Medicamento).filter(Medicamento.id == med_id).first()
        precio_base = med.precio

        for dia_offset in range(dias_transcurridos):
            fecha_venta = fecha_inicio + timedelta(days=dia_offset)
            mes = fecha_venta.month

            # Mes transcurrido desde el inicio (para calcular tendencia lineal)
            mes_offset = dia_offset / 30.0

            # Demanda base con tendencia lineal acumulada
            demanda_base = perfil["base_diaria"] + (perfil["tendencia"] * mes_offset)

            # Aplicar multiplicador de pico estacional si corresponde
            if mes in perfil["pico_meses"]:
                demanda_base *= perfil["factor_pico"]

            # Ruido gaussiano para simular variabilidad real del mercado
            ruido = np.random.normal(0, perfil["ruido_std"])
            unidades = max(0, round(demanda_base + ruido))

            # Variación de precio ±3% para simular descuentos o ajustes menores
            precio_con_variacion = round(
                precio_base * np.random.uniform(0.97, 1.03), 2
            )

            if unidades > 0:
                ventas_a_insertar.append(
                    VentaHistorica(
                        medicamento_id=med_id,
                        fecha=fecha_venta,
                        unidades_vendidas=unidades,
                        precio_unitario_en_venta=precio_con_variacion,
                    )
                )

    db.add_all(ventas_a_insertar)
    db.commit()

    total_registros = len(ventas_a_insertar)
    print(f"  → {total_registros} registros de ventas generados.")
    print("\n¡Base de datos 'pharma.db' inicializada con éxito!")
    print(f"  Medicamentos : {len(medicamentos_iniciales)}")
    print(f"  Recetas      : 1")
    print(f"  Ventas hist. : {total_registros} registros ({dias_transcurridos} días)")

except Exception as e:
    db.rollback()
    print(f"\n[ERROR] Fallo durante la inicialización: {e}")
    raise
finally:
    db.close()