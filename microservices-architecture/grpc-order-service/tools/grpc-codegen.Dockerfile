FROM python:3.12-slim

RUN pip install --no-cache-dir \
    grpcio-tools==1.75.1 \
    protobuf==6.32.1

WORKDIR /workspace
