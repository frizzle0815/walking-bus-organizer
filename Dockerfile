FROM python:3.10-slim

WORKDIR /app

# Add git for build step
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Clone repo and get revision
RUN git clone https://github.com/frizzle0815/walking-bus-organizer.git . && \
    git rev-parse HEAD > git_revision.txt && \
    rm -rf .git

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

ENV FLASK_APP=app
ENV FLASK_ENV=production

CMD python migrate.py && gunicorn --preload --config gunicorn.conf.py "app:create_app()"