# ── Etapa 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Instala dependencias en una carpeta aislada
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Etapa 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Puerto que Cloud Run espera por defecto
ENV PORT=8080

WORKDIR /app

# Copia solo las dependencias instaladas, no el build-essential
COPY --from=builder /install /usr/local

# Crea usuario no-root (appuser) — seguridad en producción
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup --no-create-home appuser

# Copia el código
COPY . .

# Ajusta permisos para appuser
RUN chown -R appuser:appgroup /app

# Cambia al usuario no-root
USER appuser

# Cloud Run usa el puerto 8080 por defecto
EXPOSE 8080

# Arranca la API con uvicorn en el puerto que Cloud Run inyecta
CMD ["sh", "-c", "uvicorn app.main_api:app --host 0.0.0.0 --port ${PORT}"]