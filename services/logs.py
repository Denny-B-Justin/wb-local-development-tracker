"""Terminal logging for the app and its scripts. Logs go to stderr only: no file, no table.

Call ``setup()`` once at an entry point (app.py, scripts/). It does nothing when the host
(gunicorn, Posit Connect) has already configured the root logger.
"""

from __future__ import annotations

import logging

import constants

# Third-party loggers that are noisy at INFO (connection pools, auth handshakes, HTTP).
QUIET = ("databricks.sql", "databricks.sdk", "urllib3", "httpx", "httpx2", "httpcore", "openai", "pyarrow", "werkzeug.serving")


def setup() -> None:
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=constants.LOG_LEVEL.upper(),
            format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )
    for name in QUIET:
        logging.getLogger(name).setLevel(logging.WARNING)
