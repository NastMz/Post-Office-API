#!/bin/sh
set -e
if [ "${SEED_DEMO_DATA:-false}" = "true" ]; then
  python -m postoffice_api.seed
fi
exec gunicorn --bind 0.0.0.0:8000 --workers 2 --threads 4 --access-logfile - wsgi:app
