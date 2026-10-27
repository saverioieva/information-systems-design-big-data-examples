FROM python:3.11-slim

# velocizza logging in container
ENV PYTHONUNBUFFERED=1

# install deps di sistema minimi (psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1) install lib condivisa
COPY libs/saga_common /tmp/saga_common
RUN pip install --no-cache-dir /tmp/saga_common

# 2) install requirements del servizio
COPY order_service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# 3) copia il codice del servizio
COPY order_service/ /app/

CMD ["python", "app.py"]
