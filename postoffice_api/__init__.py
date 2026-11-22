"""Post Office API: a REST gateway over SMTP and IMAP."""

from postoffice_api.app import create_app

__all__ = ["create_app"]
__version__ = "1.0.0"
