FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY app.py .
COPY cohesion ./cohesion
COPY coupling ./coupling

CMD ["python", "app.py", "all"]
