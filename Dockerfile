FROM python:3.12-slim

# Logs aparecem na hora no "docker logs" e horários no fuso de Brasília
ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    TZ=America/Sao_Paulo \
    PASTA_IMAGENS=/app/imagens

RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY snap_listener.py .

ENTRYPOINT ["python", "snap_listener.py"]
