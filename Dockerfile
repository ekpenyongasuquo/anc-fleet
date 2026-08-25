FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8080
EXPOSE 8080

# gunicorn for Cloud Run — single worker is fine for a scheduled batch job trigger
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app
