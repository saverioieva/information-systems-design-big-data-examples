FROM python:3.12-slim

WORKDIR /app

COPY gateway/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY gateway/src /app/src
COPY tests /app/tests
ENV PYTHONPATH=/app/src

CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
