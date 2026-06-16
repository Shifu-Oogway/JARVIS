"""Structured JSON logging."""
import logging
import sys

import structlog


def configure_logging(debug: bool = False) -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.DEBUG if debug else logging.INFO)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if debug else logging.INFO
        ),
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
