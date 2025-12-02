# Image to work on (slim for efficiency)
FROM python:3.11-slim

# Don’t create .pyc trash and logs appear immediately
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ANONYMIZED_TELEMETRY=false

# Work inside /app
WORKDIR /app

# Layer caching for faster rebuilds
# Install dependencies first
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-cache the embedding model so startup doesn't wait on downloads
RUN python - <<'PY'
from sentence_transformers import SentenceTransformer
SentenceTransformer("all-MiniLM-L6-v2")
PY

# Copy the rest of the app
COPY . .

# Expose the intended port
EXPOSE 8000

# Start FastAPI the standard way
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
