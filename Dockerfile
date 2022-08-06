FROM python:3.10-alpine

WORKDIR /post-office-api

ENV FLASK_APP app.py

ENV FLASK_RUN_HOST 0.0.0.0

COPY requirements.txt requirements.txt

RUN pip install -r requirements.txt

COPY . .

CMD ["flask", "run"]
