FROM python:3.10-slim
WORKDIR /app
COPY app.py /app/
RUN pip install --no-cache-dir Flask==3.1.1 prometheus-client==0.21.1
EXPOSE 5000
CMD ["python", "app.py"]
