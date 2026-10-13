FROM python:3.12-slim
WORKDIR /app
COPY requirements-dev.txt /app/requirements-dev.txt
RUN pip install --no-cache-dir -r /app/requirements-dev.txt
COPY checkout-service/src /app/checkout-service/src
COPY inventory-service/src /app/inventory-service/src
COPY tests /app/tests
CMD ["pytest", "-q", "/app/tests"]
