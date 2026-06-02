# Usa una imagen oficial de Python ligera
FROM python:3.11-slim

# Evita que Python escriba archivos .pyc en el disco y asegura que los logs salgan directo
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Establece el directorio de trabajo dentro del contenedor
WORKDIR /app

# Instala dependencias del sistema necesarias (por si SQLAlchemy o SQLite las requieren)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copia primero el archivo de requerimientos para aprovechar la caché de Docker
COPY requirements.txt .

# Instala las dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto del código del proyecto al contenedor
COPY . .

# Expone el puerto por si en el futuro decides volverlo una API (ej. con FastAPI)
# Por ahora, nuestro script main.py es interactivo por CLI
EXPOSE 8000

# Comando por defecto para arrancar (mantiene el entorno listo)
CMD ["python", "app/main.py"]