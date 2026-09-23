FROM python:3.11-slim
WORKDIR /app
COPY handler.py .
RUN pip install --no-cache-dir Flask==3.1.1
EXPOSE 8080
CMD ["python", "-m", "flask", "--app", "handler", "run", "--host=0.0.0.0", "--port=8080"]
