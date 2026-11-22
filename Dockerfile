FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY postoffice_api ./postoffice_api
COPY wsgi.py docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh \
 && useradd --system --create-home --uid 10001 postoffice
USER postoffice

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=10 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"

ENTRYPOINT ["./docker-entrypoint.sh"]
