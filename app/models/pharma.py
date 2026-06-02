from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, Date
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
    ventas = relationship("VentaHistorica", back_populates="medicamento")


class RecetaDigital(Base):
    __tablename__ = "recetas_digitales"

    id = Column(Integer, primary_key=True, index=True)
    codigo_receta = Column(String, unique=True, index=True, nullable=False)
    medico = Column(String, nullable=False)
    paciente = Column(String, nullable=False)
    fecha_emision = Column(DateTime, default=datetime.utcnow)

    medicamento_id = Column(Integer, ForeignKey("medicamentos.id"), nullable=False)
    medicamento = relationship("Medicamento", back_populates="recetas")


class VentaHistorica(Base):
    """
    Registro diario de unidades vendidas por medicamento.
    precio_unitario_en_venta captura el precio real al momento de la venta,
    que puede diferir del precio actual en el catálogo (descuentos, ajustes).
    Esto permite calcular revenue proyectado y margen real.
    """
    __tablename__ = "ventas_historicas"

    id = Column(Integer, primary_key=True, index=True)
    medicamento_id = Column(Integer, ForeignKey("medicamentos.id"), nullable=False)
    fecha = Column(Date, nullable=False, index=True)
    unidades_vendidas = Column(Integer, nullable=False)
    precio_unitario_en_venta = Column(Float, nullable=False)

    medicamento = relationship("Medicamento", back_populates="ventas")