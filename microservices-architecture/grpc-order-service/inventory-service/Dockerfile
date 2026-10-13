FROM python:3.12-slim
WORKDIR /app
COPY inventory-service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY proto /app/proto
RUN mkdir -p /app/generated && \
    python -m grpc_tools.protoc -I/app/proto \
      --python_out=/app/generated \
      --grpc_python_out=/app/generated \
      /app/proto/inventory.proto
COPY inventory-service/src /app/src
ENV PYTHONPATH=/app/src:/app/generated
CMD ["python", "-m", "inventory_service.main"]
