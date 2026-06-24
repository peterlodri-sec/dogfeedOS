FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py .

VOLUME ["/data"]
ENV DB_PATH=/data/dogfeed.db

CMD ["python", "main.py"]
