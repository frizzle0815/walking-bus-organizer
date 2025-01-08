FROM python:3.10-slim

# Create monkey_patch.py first
RUN echo "from gevent import monkey; monkey.patch_all()" > /app/monkey_patch.py

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FLASK_APP=app
ENV FLASK_ENV=production

# Modified CMD to use monkey_patch.py
CMD python migrate.py && gunicorn --preload --config gunicorn.conf.py --pythonpath /app "app:create_app()"