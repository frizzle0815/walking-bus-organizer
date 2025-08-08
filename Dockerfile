FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FLASK_APP=app
ENV FLASK_ENV=production

# Default command - kann in docker-compose.yml überschrieben werden
CMD python migrate.py && gunicorn --preload --config gunicorn.conf.py "app:create_app()"
