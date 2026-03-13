"""
Tests — Webhook Router
"""
import hashlib
import hmac
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

WEBHOOK_SECRET = "test-secret"


def _sign(payload: bytes, secret: str = WEBHOOK_SECRET) -> str:
    mac = hmac.new(secret.encode(), msg=payload, digestmod=hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


SAMPLE_PR_EVENT = {
    "action": "opened",
    "number": 1,
    "pull_request": {
        "number": 1,
        "title": "Add feature X",
        "body": "This PR adds feature X",
        "state": "open",
        "draft": False,
        "head": {"sha": "abc123", "ref": "feature/x"},
        "base": {"ref": "main"},
        "user": {"login": "developer", "id": 1},
        "html_url": "https://github.com/org/repo/pull/1",
        "diff_url": "https://github.com/org/repo/pull/1.diff",
        "patch_url": "https://github.com/org/repo/pull/1.patch",
        "additions": 50,
        "deletions": 10,
        "changed_files": 3,
    },
    "repository": {
        "id": 123,
        "name": "repo",
        "full_name": "org/repo",
        "private": False,
        "default_branch": "main",
        "clone_url": "https://github.com/org/repo.git",
        "html_url": "https://github.com/org/repo",
    },
    "installation": {"id": 456},
    "sender": {"login": "developer", "id": 1},
}


@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.setenv("GITHUB_APP_ID", "test-app-id")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY", "test-private-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")


def test_health_check():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_webhook_missing_signature():
    response = client.post(
        "/api/v1/webhook/github",
        content=json.dumps(SAMPLE_PR_EVENT),
        headers={"X-GitHub-Event": "pull_request"},
    )
    assert response.status_code == 401


def test_webhook_invalid_signature():
    body = json.dumps(SAMPLE_PR_EVENT).encode()
    response = client.post(
        "/api/v1/webhook/github",
        content=body,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": "sha256=invalidsig",
        },
    )
    assert response.status_code == 401


def test_webhook_ignores_non_pr_event():
    body = json.dumps({"action": "created"}).encode()
    response = client.post(
        "/api/v1/webhook/github",
        content=body,
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": _sign(body),
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


def test_webhook_ignores_draft_pr():
    event = dict(SAMPLE_PR_EVENT)
    event["pull_request"] = {**SAMPLE_PR_EVENT["pull_request"], "draft": True}
    body = json.dumps(event).encode()
    response = client.post(
        "/api/v1/webhook/github",
        content=body,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": _sign(body),
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "skipped"


@patch("app.api.webhook_router._run_review", new_callable=AsyncMock)
def test_webhook_accepts_valid_pr(mock_review):
    body = json.dumps(SAMPLE_PR_EVENT).encode()
    response = client.post(
        "/api/v1/webhook/github",
        content=body,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": _sign(body),
        },
    )
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "accepted"
    assert data["pr_number"] == 1
