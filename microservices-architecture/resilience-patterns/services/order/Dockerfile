FROM python:3.12-slim

WORKDIR /app
COPY services/order/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY services/common /app/common
COPY services/order/main.py /app/main.py
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
