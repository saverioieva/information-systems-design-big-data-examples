FROM python:3.12-slim

WORKDIR /app
COPY services/kitchen/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY services/common /app/common
COPY services/kitchen/main.py /app/main.py
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
