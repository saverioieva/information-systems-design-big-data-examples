FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY libs/saga_common /tmp/saga_common
RUN pip install --no-cache-dir /tmp/saga_common

COPY accounting_service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY accounting_service/ /app/

CMD ["python", "app.py"]
