"""
AWS Lambda Handler — Wraps the FastAPI app using Mangum
Enables serverless deployment via AWS Lambda + API Gateway.
"""
import json
import logging
import os

from mangum import Mangum

# Configure logging for Lambda
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

# Import app after logging is set up
from app.main import app  # noqa: E402

# Mangum adapts ASGI (FastAPI) to AWS Lambda + API Gateway events
handler = Mangum(app, lifespan="off")


def lambda_handler(event: dict, context) -> dict:
    """
    AWS Lambda entry point.
    Delegates to Mangum which translates the API Gateway event
    into an ASGI-compatible request and back.
    """
    logger.info(
        "Lambda invoked | request_id=%s | path=%s | method=%s",
        getattr(context, "aws_request_id", "local"),
        event.get("path", event.get("rawPath", "/")),
        event.get("httpMethod", event.get("requestContext", {}).get("http", {}).get("method", "?")),
    )
    return handler(event, context)
