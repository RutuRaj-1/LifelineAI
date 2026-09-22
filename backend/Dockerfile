FROM python:3.11-slim

# tesseract-ocr: OCR fallback for scanned images/PDFs (see ai/ocr.py)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr libpq-dev gcc curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY ai ai
COPY backend backend
COPY database database

ENV PYTHONUNBUFFERED=1
WORKDIR /srv
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
