"""
PR Review Service — Orchestrates the full review pipeline
"""
import logging
from typing import Optional

from app.models.github_models import PullRequestEvent
from app.models.review_models import ReviewResult
from app.services.ai_reviewer import AIReviewOrchestrator
from app.services.github_client import GitHubAppClient

logger = logging.getLogger(__name__)


class PRReviewService:
    """
    Coordinates fetching PR data, running AI review, and posting results.
    """

    def __init__(self):
        self.github = GitHubAppClient()
        self.ai = AIReviewOrchestrator()

    async def process_pull_request_event(self, event: PullRequestEvent) -> Optional[ReviewResult]:
        pr = event.pull_request
        repo = event.repository
        installation_id = str(event.installation["id"]) if event.installation else ""
        owner, repo_name = repo.full_name.split("/", 1)

        logger.info("Processing PR #%d on %s", pr.number, repo.full_name)

        # Mark commit as pending
        await self.github.set_commit_status(
            owner=owner,
            repo=repo_name,
            sha=pr.head["sha"],
            state="pending",
            description="Code review in progress…",
            installation_id=installation_id,
        )

        try:
            files = await self.github.get_pr_files(
                owner=owner,
                repo=repo_name,
                pr_number=pr.number,
                installation_id=installation_id,
            )

            result = await self.ai.review(
                pr_title=pr.title,
                pr_body=pr.body or "",
                files=files,
            )
            result.pr_number = pr.number
            result.repo_full_name = repo.full_name

            await self.github.post_review(
                owner=owner,
                repo=repo_name,
                pr_number=pr.number,
                review_result=result,
                installation_id=installation_id,
            )

            commit_state = "failure" if result.critical_count > 0 else "success"
            commit_desc = _commit_status_description(result)
            await self.github.set_commit_status(
                owner=owner,
                repo=repo_name,
                sha=pr.head["sha"],
                state=commit_state,
                description=commit_desc,
                installation_id=installation_id,
            )

            logger.info(
                "Review complete for PR #%d: %s | %d issues (%d critical)",
                pr.number, result.decision, result.total_issues, result.critical_count,
            )
            return result

        except Exception as exc:
            logger.exception("Review failed for PR #%d: %s", pr.number, exc)
            await self.github.set_commit_status(
                owner=owner,
                repo=repo_name,
                sha=pr.head["sha"],
                state="error",
                description="Code review failed — check bot logs",
                installation_id=installation_id,
            )
            raise


def _commit_status_description(result: ReviewResult) -> str:
    if result.total_issues == 0:
        return "✅ No issues found"
    parts = []
    if result.critical_count:
        parts.append(f"{result.critical_count} critical")
    if result.high_count:
        parts.append(f"{result.high_count} high")
    if result.medium_count:
        parts.append(f"{result.medium_count} medium")
    if result.low_count:
        parts.append(f"{result.low_count} low")
    return f"Found {result.total_issues} issues: {', '.join(parts)}"
