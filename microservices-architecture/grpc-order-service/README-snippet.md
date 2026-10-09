### gRPC Order Service

[`grpc-order-service/`](grpc-order-service/) demonstrates Protocol Buffers, generated gRPC stubs/interfaces, Unary and Streaming RPCs, and a practical **REST outside / gRPC inside** architecture. A FastAPI public service exposes JSON/HTTP to external clients and communicates with an internal hexagonal Order Service over gRPC/HTTP2.
