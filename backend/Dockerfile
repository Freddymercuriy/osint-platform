FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# DEV=1 — test bog'liqliklari (pytest) ham o'rnatiladi (docker-compose.yml lokal ishlab chiqish uchun beradi)
ARG DEV=0
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && if [ "$DEV" = "1" ]; then pip install --no-cache-dir -r requirements-dev.txt; fi

COPY . .

EXPOSE 8000
# Avval migratsiyalar (alembic upgrade head), keyin API
CMD ["sh", "scripts/start.sh"]
