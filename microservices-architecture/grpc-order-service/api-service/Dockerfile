FROM python:3.12-slim
WORKDIR /app
COPY api-service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY proto /app/proto
RUN mkdir -p /app/generated && \
    python -m grpc_tools.protoc -I/app/proto \
      --python_out=/app/generated \
      --grpc_python_out=/app/generated \
      /app/proto/order.proto
COPY api-service/app /app/app
ENV PYTHONPATH=/app:/app/generated
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
