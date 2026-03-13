"""
Webhook Router — Receives and dispatches GitHub webhook events
"""
import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status

from app.models.github_models import PullRequestEvent
from app.services.pr_review_service import PRReviewService
from app.utils.signature_verifier import verify_github_signature

logger = logging.getLogger(__name__)
router = APIRouter()

REVIEWABLE_ACTIONS = {"opened", "synchronize", "reopened", "ready_for_review"}


@router.post("/webhook/github", status_code=status.HTTP_202_ACCEPTED)
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: str = Header(default=""),
    body: bytes = Depends(verify_github_signature),
):
    """
    Receives all GitHub App webhook events.
    Only processes pull_request events with reviewable actions.
    Signature is verified before this handler runs (via dependency).
    """
    if x_github_event != "pull_request":
        logger.debug("Ignoring non-PR event: %s", x_github_event)
        return {"status": "ignored", "event": x_github_event}

    import json
    payload = json.loads(body)
    action = payload.get("action", "")

    if action not in REVIEWABLE_ACTIONS:
        logger.debug("Ignoring PR action: %s", action)
        return {"status": "ignored", "action": action}

    # Skip draft PRs
    pr_data = payload.get("pull_request", {})
    if pr_data.get("draft", False):
        logger.info("Skipping draft PR #%s", pr_data.get("number"))
        return {"status": "skipped", "reason": "draft"}

    try:
        event = PullRequestEvent(**payload)
    except Exception as exc:
        logger.error("Failed to parse PR event: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid payload: {exc}",
        )

    background_tasks.add_task(_run_review, event)
    return {
        "status": "accepted",
        "pr_number": event.number,
        "action": action,
    }


async def _run_review(event: PullRequestEvent):
    service = PRReviewService()
    try:
        await service.process_pull_request_event(event)
    except Exception:
        logger.exception(
            "Unhandled error reviewing PR #%d on %s",
            event.number,
            event.repository.full_name,
        )
