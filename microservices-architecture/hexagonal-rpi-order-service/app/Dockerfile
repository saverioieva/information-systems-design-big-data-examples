FROM python:3.12-slim

WORKDIR /app

COPY app/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app/src ./src
COPY tests ./tests

ENV PYTHONPATH=/app/src

# Default adapter. Docker Compose overrides this command for the Flask variant.
CMD ["uvicorn", "order_service.main_fastapi:app", "--host", "0.0.0.0", "--port", "8000"]
