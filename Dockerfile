# ============================================================
# Cash Tel — Image Docker
# ============================================================
FROM python:3.12-slim

WORKDIR /app

# Variables Python recommandées
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Dépendances système pour psycopg2 et Pillow
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Installation des dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du code source
COPY . .

# Création des dossiers médias et statiques
RUN mkdir -p /app/media/qr_codes /app/staticfiles

EXPOSE 8000
