FROM python:3.12-slim
WORKDIR /app
COPY order-service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY proto /app/proto
RUN mkdir -p /app/generated && \
    python -m grpc_tools.protoc -I/app/proto \
      --python_out=/app/generated \
      --grpc_python_out=/app/generated \
      /app/proto/order.proto
COPY order-service/app /app/app
ENV PYTHONPATH=/app:/app/generated
CMD ["python", "-m", "app.main"]
