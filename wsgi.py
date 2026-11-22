"""WSGI entry point: ``gunicorn wsgi:app``."""

from postoffice_api import create_app

app = create_app()
