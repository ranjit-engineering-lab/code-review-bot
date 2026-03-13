"""
Domain Models — GitHub Webhook Payloads
"""
from typing import Optional
from pydantic import BaseModel


class GitHubUser(BaseModel):
    login: str
    id: int


class GitHubRepository(BaseModel):
    id: int
    name: str
    full_name: str
    private: bool
    default_branch: str = "main"
    clone_url: str
    html_url: str


class GitHubPullRequest(BaseModel):
    number: int
    title: str
    body: Optional[str] = None
    state: str
    head: dict
    base: dict
    user: GitHubUser
    html_url: str
    diff_url: str
    patch_url: str
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0


class PullRequestEvent(BaseModel):
    action: str
    number: int
    pull_request: GitHubPullRequest
    repository: GitHubRepository
    installation: Optional[dict] = None
    sender: Optional[GitHubUser] = None
