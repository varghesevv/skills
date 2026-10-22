"""The version of this build. Set when the image is built (APP_VERSION); "dev" locally."""

import os

APP_VERSION = os.environ.get("APP_VERSION", "dev")
