"""Environment-selected entry point shared by all bounded FastAPI services."""

import os

from proactive_core.api import create_app

SERVICE_NAME = os.getenv("APP_SERVICE_NAME", "all")
app = create_app(SERVICE_NAME)
