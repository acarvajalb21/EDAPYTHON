FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8080

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY . /app/dash_salud

EXPOSE 8080
CMD exec gunicorn --bind 0.0.0.0:${PORT} --workers 2 --threads 4 --timeout 120 dash_salud.app:server
