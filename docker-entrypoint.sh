#!/bin/sh
set -e
if [ "${SEED_DEMO_DATA:-false}" = "true" ]; then
  python -m postoffice_api.seed
fi
exec gunicorn --bind 0.0.0.0:8000 --workers 1 --threads 8 --access-logfile - wsgi:app
