FROM python:3.12-slim

WORKDIR /client

COPY client/requirements.txt /client/requirements.txt
RUN pip install --no-cache-dir -r /client/requirements.txt

COPY client/rpi_client.py /client/rpi_client.py

CMD ["python", "/client/rpi_client.py"]
