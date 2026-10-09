FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir grpcio==1.75.1 grpcio-tools==1.75.1 protobuf==6.32.1
COPY proto /app/proto
RUN mkdir -p /app/generated && \
    python -m grpc_tools.protoc -I/app/proto \
      --python_out=/app/generated \
      --grpc_python_out=/app/generated \
      /app/proto/order.proto
COPY demo-clients /app/clients
ENV PYTHONPATH=/app/generated:/app/clients
WORKDIR /app/clients
ENTRYPOINT ["python"]
