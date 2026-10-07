FROM python:3.12-slim

WORKDIR /app

COPY app/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app/src ./src
COPY tests ./tests

ENV PYTHONPATH=/app/src

CMD ["uvicorn", "order_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
