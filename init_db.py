# init_db.py
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.database import engine, Base, SessionLocal
from app.models.pharma import Medicamento, RecetaDigital

print("=== INICIALIZANDO BASE DE DATOS LOCAL (SQLITE) ===")

# 1. Crear las tablas físicamente basándose en los modelos importados
print("Creando tablas en pharma.db...")
Base.metadata.drop_all(bind=engine)  # Limpia la DB por si acaso para empezar desde cero
Base.metadata.create_all(bind=engine)

# 2. Abrir una sesión para insertar los datos de prueba (Seed)
db = SessionLocal()

try:
    print("Insertando catálogo de medicamentos de prueba...")
    
    # Lista de medicamentos iniciales
    medicamentos_iniciales = [
        Medicamento(
            nombre="Paracetamol 500mg", 
            compuesto_activo="Paracetamol", 
            precio=45.50, 
            stock=150, 
            requiere_receta=False
        ),
        Medicamento(
            nombre="Ibuprofeno 400mg", 
            compuesto_activo="Ibuprofeno", 
            precio=62.00, 
            stock=80, 
            requiere_receta=False
        ),
        Medicamento(
            nombre="Amoxicilina 500mg", 
            compuesto_activo="Amoxicilina", 
            precio=120.00, 
            stock=35, 
            requiere_receta=True  # Requiere validación de receta
        ),
        Medicamento(
            nombre="Clonazepam 2mg", 
            compuesto_activo="Clonazepam", 
            precio=210.00, 
            stock=12, 
            requiere_receta=True  # Medicamento controlado
        ),
        Medicamento(
            nombre="Loratadina 10mg", 
            compuesto_activo="Loratadina", 
            precio=38.00, 
            stock=200, 
            requiere_receta=False
        ),
        Medicamento(
            nombre="Insulina Glargina 100 UI/ml", 
            compuesto_activo="Insulina", 
            precio=480.00, 
            stock=25, 
            requiere_receta=True  # La insulina requiere receta o control médico
        )
    ]
    
    db.add_all(medicamentos_iniciales)
    db.commit() # Guardamos los cambios de los medicamentos
    
    # 3. Insertar una receta digital de prueba vinculada a la Amoxicilina (ID 3)
    print("Insertando receta digital de prueba...")
    receta_prueba = RecetaDigital(
        codigo_receta="REC-9988-77",
        medico="Dr. Alejandro Cárdenas (Céd. 1234567)",
        paciente="Carlos López Mendoza",
        medicamento_id=3 # Vinculado directamente a la Amoxicilina
    )
    
    db.add(receta_prueba)
    db.commit()
    
    print("\n¡Base de datos 'pharma.db' creada e inyectada con éxito!")

except Exception as e:
    db.rollback()
    print(f"\n[ERROR] Ocurrió un fallo durante la inicialización: {e}")
finally:
    db.close()