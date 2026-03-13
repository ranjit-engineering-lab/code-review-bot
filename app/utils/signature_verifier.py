"""
GitHub Webhook Signature Verification
"""
import hashlib
import hmac
import logging

from fastapi import HTTPException, Request, status

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def verify_github_signature(request: Request) -> bytes:
    """
    Verify the HMAC-SHA256 signature sent by GitHub on every webhook.
    Raises HTTP 401 if the signature is missing or invalid.
    """
    signature_header = request.headers.get("X-Hub-Signature-256")
    if not signature_header:
        logger.warning("Missing X-Hub-Signature-256 header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing webhook signature",
        )

    body = await request.body()
    expected_signature = _compute_signature(body, settings.GITHUB_WEBHOOK_SECRET)

    if not hmac.compare_digest(signature_header, expected_signature):
        logger.warning("Invalid webhook signature — possible spoofing attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    return body


def _compute_signature(body: bytes, secret: str) -> str:
    mac = hmac.new(secret.encode(), msg=body, digestmod=hashlib.sha256)
    return f"sha256={mac.hexdigest()}"
