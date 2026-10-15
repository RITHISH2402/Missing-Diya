FROM mcr.microsoft.com/playwright/python:v1.64.0-noble

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

CMD ["sh", "-c", "gunicorn --workers 1 --threads 4 --timeout 30 --bind 0.0.0.0:${PORT:-10000} app:app"]
