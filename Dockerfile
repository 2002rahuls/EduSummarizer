FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Install system dependencies needed by some Python packages (Tesseract, Poppler, imaging libs)
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
  build-essential \
  ca-certificates \
  git \
  libglib2.0-0 \
  libgl1 \
  tesseract-ocr \
  poppler-utils \
  libjpeg-dev \
  zlib1g-dev \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create a non-root user for security
RUN useradd --create-home appuser || true

COPY requirements.txt ./

# Upgrade pip tools and install Python deps
RUN pip install --upgrade pip setuptools wheel \
  && pip install --no-cache-dir -r requirements.txt

# Copy app sources
COPY . .

# Ensure files are owned by the non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

EXPOSE 8080

# Use a shell entry so environment variables like $PORT are expanded.
# Point uvicorn at the FastAPI app defined in api/summarize_api.py
ENTRYPOINT sh -c "uvicorn api.summarize_api:app --host 0.0.0.0 --port ${PORT} --workers ${WORKERS:-1}"
