FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATA_STORAGE_PATH=/app/data/bot_data.json

WORKDIR /app

# Install system dependencies if required
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY config.py bale_client.py eitaa_client.py forwarder.py dashboard.py bot.py ./

# Create directory for persistent data
RUN mkdir -p /app/data

VOLUME ["/app/data"]

CMD ["python", "bot.py"]
