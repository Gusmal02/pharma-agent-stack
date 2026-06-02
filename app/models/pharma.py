from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Medicamento(Base):
    __tablename__ = "medicamentos"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, unique=True, index=True, nullable=False)
    compuesto_activo = Column(String, nullable=False)
    precio = Column(Float, nullable=False)
    stock = Column(Integer, default=0)
    requiere_receta = Column(Boolean, default=False)

    recetas = relationship("RecetaDigital", back_populates="medicamento")

class RecetaDigital(Base):
    __tablename__ = "recetas_digitales"

    id = Column(Integer, primary_key=True, index=True)
    codigo_receta = Column(String, unique=True, index=True, nullable=False)
    medico = Column(String, nullable=False)
    paciente = Column(String, nullable=False)
    fecha_emision = Column(DateTime, default=datetime.utcnow)

    medicamento_id = Column(Integer, ForeignKey("medicamentos.id"), nullable=False)
    medicamento = relationship("Medicamento", back_populates="recetas")