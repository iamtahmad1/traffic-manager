# Dockerfile for Cache Invalidation Consumer
FROM python:3.11-slim as builder

WORKDIR /app

RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /usr/local /usr/local

# Copy shared source code
COPY src/ ./src/
# Copy service entry point
COPY services/cache-invalidation-consumer/main.py ./main.py

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

CMD ["python", "main.py"]
