"""
Domain Models — Code Review Results & Findings
"""
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FindingCategory(str, Enum):
    SECURITY = "SECURITY"
    PERFORMANCE = "PERFORMANCE"
    STYLE = "STYLE"
    BUG = "BUG"
    MAINTAINABILITY = "MAINTAINABILITY"


class CodeFinding(BaseModel):
    category: FindingCategory
    severity: Severity
    file_path: str
    line_number: Optional[int] = None
    end_line_number: Optional[int] = None
    title: str
    description: str
    suggestion: Optional[str] = None
    code_snippet: Optional[str] = None
    rule_id: Optional[str] = None


class FileDiff(BaseModel):
    filename: str
    status: str  # added, modified, removed, renamed
    additions: int
    deletions: int
    patch: Optional[str] = None
    raw_url: Optional[str] = None
    blob_url: Optional[str] = None


class ReviewDecision(str, Enum):
    APPROVE = "APPROVE"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    COMMENT = "COMMENT"


class ReviewResult(BaseModel):
    pr_number: int
    repo_full_name: str
    decision: ReviewDecision
    summary: str
    findings: List[CodeFinding] = Field(default_factory=list)
    security_findings: List[CodeFinding] = Field(default_factory=list)
    performance_findings: List[CodeFinding] = Field(default_factory=list)
    style_findings: List[CodeFinding] = Field(default_factory=list)
    total_issues: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0

    def compute_counts(self):
        all_findings = self.findings + self.security_findings + self.performance_findings + self.style_findings
        self.total_issues = len(all_findings)
        self.critical_count = sum(1 for f in all_findings if f.severity == Severity.CRITICAL)
        self.high_count = sum(1 for f in all_findings if f.severity == Severity.HIGH)
        self.medium_count = sum(1 for f in all_findings if f.severity == Severity.MEDIUM)
        self.low_count = sum(1 for f in all_findings if f.severity == Severity.LOW)
