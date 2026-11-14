#!/bin/sh
# Konteyner ishga tushishi: migratsiyalar → API.
set -e
cd "$(dirname "$0")/.."
python scripts/migrate.py
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
