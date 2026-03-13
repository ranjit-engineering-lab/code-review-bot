"""
Tests — Review Models
"""
import pytest
from app.models.review_models import (
    CodeFinding,
    FindingCategory,
    ReviewDecision,
    ReviewResult,
    Severity,
)


def _make_finding(severity: Severity, category: FindingCategory = FindingCategory.SECURITY) -> CodeFinding:
    return CodeFinding(
        category=category,
        severity=severity,
        file_path="app/main.py",
        line_number=42,
        title="Test finding",
        description="Test description",
    )


def test_review_result_compute_counts_empty():
    result = ReviewResult(
        pr_number=1,
        repo_full_name="org/repo",
        decision=ReviewDecision.APPROVE,
        summary="LGTM",
    )
    result.compute_counts()
    assert result.total_issues == 0
    assert result.critical_count == 0


def test_review_result_compute_counts_mixed():
    result = ReviewResult(
        pr_number=1,
        repo_full_name="org/repo",
        decision=ReviewDecision.REQUEST_CHANGES,
        summary="Issues found",
        security_findings=[
            _make_finding(Severity.CRITICAL),
            _make_finding(Severity.HIGH),
        ],
        performance_findings=[
            _make_finding(Severity.MEDIUM, FindingCategory.PERFORMANCE),
        ],
        style_findings=[
            _make_finding(Severity.LOW, FindingCategory.STYLE),
            _make_finding(Severity.LOW, FindingCategory.STYLE),
        ],
    )
    result.compute_counts()
    assert result.total_issues == 5
    assert result.critical_count == 1
    assert result.high_count == 1
    assert result.medium_count == 1
    assert result.low_count == 2


def test_severity_enum_values():
    assert Severity.LOW == "LOW"
    assert Severity.CRITICAL == "CRITICAL"


def test_finding_category_enum():
    assert FindingCategory.SECURITY == "SECURITY"
    assert FindingCategory.PERFORMANCE == "PERFORMANCE"
