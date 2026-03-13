"""
GitHub App Client — Authentication & REST API Interactions
"""
import logging
import time
from typing import List, Optional

import httpx
import jwt

from app.core.config import get_settings
from app.models.github_models import GitHubPullRequest
from app.models.review_models import FileDiff, ReviewDecision, ReviewResult

logger = logging.getLogger(__name__)
settings = get_settings()

GITHUB_API_BASE = "https://api.github.com"


class GitHubAppClient:
    """Handles GitHub App JWT auth + installation token lifecycle."""

    def __init__(self):
        self._installation_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    def _generate_jwt(self) -> str:
        now = int(time.time())
        payload = {
            "iat": now - 60,
            "exp": now + (10 * 60),
            "iss": settings.GITHUB_APP_ID,
        }
        private_key = settings.GITHUB_PRIVATE_KEY.replace("\\n", "\n")
        return jwt.encode(payload, private_key, algorithm="RS256")

    async def _get_installation_token(self, installation_id: str) -> str:
        if self._installation_token and time.time() < self._token_expires_at - 60:
            return self._installation_token

        app_jwt = self._generate_jwt()
        url = f"{GITHUB_API_BASE}/app/installations/{installation_id}/access_tokens"
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json",
                },
            )
            response.raise_for_status()
            data = response.json()
            self._installation_token = data["token"]
            self._token_expires_at = time.time() + 3600
            return self._installation_token

    async def _auth_headers(self, installation_id: str) -> dict:
        token = await self._get_installation_token(installation_id)
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def get_pull_request(
        self, owner: str, repo: str, pr_number: int, installation_id: str
    ) -> GitHubPullRequest:
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}"
        headers = await self._auth_headers(installation_id)
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return GitHubPullRequest(**resp.json())

    async def get_pr_files(
        self, owner: str, repo: str, pr_number: int, installation_id: str
    ) -> List[FileDiff]:
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/files"
        headers = await self._auth_headers(installation_id)
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, params={"per_page": 100})
            resp.raise_for_status()
            return [FileDiff(**f) for f in resp.json()]

    async def post_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        review_result: ReviewResult,
        installation_id: str,
    ) -> dict:
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
        headers = await self._auth_headers(installation_id)
        comments = _build_review_comments(review_result)

        body = {
            "body": review_result.summary,
            "event": review_result.decision.value,
            "comments": comments,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            logger.info(
                "Posted review to %s/%s#%d: %s",
                owner, repo, pr_number, review_result.decision,
            )
            return resp.json()

    async def set_commit_status(
        self,
        owner: str,
        repo: str,
        sha: str,
        state: str,
        description: str,
        installation_id: str,
    ):
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/statuses/{sha}"
        headers = await self._auth_headers(installation_id)
        body = {
            "state": state,
            "description": description[:140],
            "context": "code-review-bot",
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()


def _build_review_comments(review_result: ReviewResult) -> List[dict]:
    """Convert CodeFinding objects into GitHub review comment dicts."""
    comments = []
    all_findings = (
        review_result.findings
        + review_result.security_findings
        + review_result.performance_findings
        + review_result.style_findings
    )
    for finding in all_findings:
        if finding.line_number is None:
            continue
        body = (
            f"**[{finding.severity}] {finding.category} — {finding.title}**\n\n"
            f"{finding.description}\n"
        )
        if finding.suggestion:
            body += f"\n💡 **Suggestion:** {finding.suggestion}"
        comment: dict = {
            "path": finding.file_path,
            "line": finding.line_number,
            "body": body,
        }
        if finding.end_line_number and finding.end_line_number != finding.line_number:
            comment["start_line"] = finding.line_number
            comment["line"] = finding.end_line_number
        comments.append(comment)
    return comments
