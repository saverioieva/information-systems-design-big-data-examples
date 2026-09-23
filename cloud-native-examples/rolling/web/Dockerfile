FROM python:3.12-alpine

ARG APP_VERSION=v1
ENV APP_VERSION=${APP_VERSION}

WORKDIR /app
COPY app.py /app/app.py

RUN pip install --no-cache-dir Flask==3.1.1

EXPOSE 5000
CMD ["python", "app.py"]
