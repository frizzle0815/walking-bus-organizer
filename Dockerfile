FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FLASK_APP=app
ENV FLASK_ENV=production

CMD python migrate.py && gunicorn --config gunicorn.conf.py "app:create_app()"
