# Single-stage image for the FastAPI app. Small, reproducible, runs as non-root.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System libraries needed by opencv-python-headless (OpenMP + glib). Kept minimal.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first so this layer is cached when only app code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY app ./app
COPY frontend ./frontend
COPY scripts ./scripts

# Run as an unprivileged user.
RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

# In production you'd typically run multiple workers behind a proxy.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
