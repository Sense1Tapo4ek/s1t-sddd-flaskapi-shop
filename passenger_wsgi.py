"""
CPanel / Phusion Passenger entry point.

CPanel's "Setup Python App" feature expects an `application` callable
in passenger_wsgi.py at the project root.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
os.environ.setdefault("ROOT_APP_ENV", "prod")
os.environ.setdefault("FLASK_DEBUG", "0")

from root.entrypoints.api import create_app  # noqa: E402

application = create_app()
