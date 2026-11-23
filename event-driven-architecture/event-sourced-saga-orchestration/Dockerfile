FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /code
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY lab/ ./lab/
COPY scripts/ ./scripts/
COPY tests/ ./tests/
CMD ["uvicorn", "lab.main:app", "--host", "0.0.0.0", "--port", "8000"]
