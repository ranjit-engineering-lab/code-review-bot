"""
AI Code Review Orchestrator — LangChain + OpenAI
"""
import json
import logging
from typing import List

from langchain.callbacks import get_openai_callback
from langchain.chains import LLMChain
from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_openai import ChatOpenAI

from app.core.config import get_settings
from app.models.review_models import (
    CodeFinding,
    FileDiff,
    FindingCategory,
    ReviewDecision,
    ReviewResult,
    Severity,
)
from app.utils.diff_parser import extract_code_context

logger = logging.getLogger(__name__)
settings = get_settings()


class AIReviewOrchestrator:
    """
    Orchestrates multi-pass AI code review using LangChain chains:
    1. Security analysis pass
    2. Performance analysis pass
    3. Style/maintainability pass
    4. Summary & decision pass
    """

    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=settings.OPENAI_TEMPERATURE,
            max_tokens=settings.OPENAI_MAX_TOKENS,
            openai_api_key=settings.OPENAI_API_KEY,
        )

    async def review(
        self, pr_title: str, pr_body: str, files: List[FileDiff]
    ) -> ReviewResult:
        filtered_files = [f for f in files if f.patch and _is_reviewable(f.filename)]
        truncated = filtered_files[: settings.MAX_FILES_PER_PR]

        diff_context = _build_diff_context(truncated)

        security_findings: List[CodeFinding] = []
        performance_findings: List[CodeFinding] = []
        style_findings: List[CodeFinding] = []

        with get_openai_callback() as cb:
            if settings.ENABLE_SECURITY_CHECKS:
                security_findings = await self._run_security_pass(diff_context)

            if settings.ENABLE_PERFORMANCE_CHECKS:
                performance_findings = await self._run_performance_pass(diff_context)

            if settings.ENABLE_STYLE_CHECKS:
                style_findings = await self._run_style_pass(diff_context)

            logger.info(
                "OpenAI usage — tokens: %d, cost: $%.4f", cb.total_tokens, cb.total_cost
            )

        all_findings = security_findings + performance_findings + style_findings
        decision = _compute_decision(all_findings)
        summary = await self._generate_summary(
            pr_title, pr_body, all_findings, decision, diff_context
        )

        result = ReviewResult(
            pr_number=0,
            repo_full_name="",
            decision=decision,
            summary=summary,
            security_findings=security_findings,
            performance_findings=performance_findings,
            style_findings=style_findings,
        )
        result.compute_counts()
        return result

    async def _run_security_pass(self, diff_context: str) -> List[CodeFinding]:
        prompt = _security_prompt()
        chain = LLMChain(llm=self.llm, prompt=prompt)
        raw = await chain.arun(diff=diff_context)
        return _parse_findings(raw, FindingCategory.SECURITY)

    async def _run_performance_pass(self, diff_context: str) -> List[CodeFinding]:
        prompt = _performance_prompt()
        chain = LLMChain(llm=self.llm, prompt=prompt)
        raw = await chain.arun(diff=diff_context)
        return _parse_findings(raw, FindingCategory.PERFORMANCE)

    async def _run_style_pass(self, diff_context: str) -> List[CodeFinding]:
        prompt = _style_prompt()
        chain = LLMChain(llm=self.llm, prompt=prompt)
        raw = await chain.arun(diff=diff_context)
        return _parse_findings(raw, FindingCategory.STYLE)

    async def _generate_summary(
        self,
        pr_title: str,
        pr_body: str,
        findings: List[CodeFinding],
        decision: ReviewDecision,
        diff_context: str,
    ) -> str:
        findings_text = "\n".join(
            f"- [{f.severity}] {f.category}: {f.title} ({f.file_path})"
            for f in findings
        ) or "No significant issues found."

        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessagePromptTemplate.from_template(_SUMMARY_SYSTEM),
                HumanMessagePromptTemplate.from_template(_SUMMARY_HUMAN),
            ]
        )
        chain = LLMChain(llm=self.llm, prompt=prompt)
        return await chain.arun(
            pr_title=pr_title,
            pr_body=pr_body or "No description provided.",
            findings=findings_text,
            decision=decision.value,
            diff=diff_context[:3000],
        )


# ── Helpers ──────────────────────────────────────────────────────────────────

def _is_reviewable(filename: str) -> bool:
    skip_extensions = {".lock", ".png", ".jpg", ".gif", ".svg", ".ico", ".woff", ".ttf"}
    skip_prefixes = ("dist/", "build/", "node_modules/", ".github/", "migrations/")
    ext = "." + filename.rsplit(".", 1)[-1] if "." in filename else ""
    return ext not in skip_extensions and not any(
        filename.startswith(p) for p in skip_prefixes
    )


def _build_diff_context(files: List[FileDiff]) -> str:
    parts = []
    total_lines = 0
    for f in files:
        if not f.patch:
            continue
        patch_lines = f.patch.splitlines()
        remaining = settings.MAX_DIFF_LINES - total_lines
        if remaining <= 0:
            break
        truncated_patch = "\n".join(patch_lines[:remaining])
        parts.append(f"### File: {f.filename}\n```diff\n{truncated_patch}\n```")
        total_lines += len(patch_lines)
    return "\n\n".join(parts)


def _parse_findings(raw: str, category: FindingCategory) -> List[CodeFinding]:
    """Parse JSON array of findings from LLM response."""
    findings = []
    try:
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start == -1 or end == 0:
            return findings
        data = json.loads(raw[start:end])
        for item in data:
            try:
                item["category"] = category.value
                findings.append(CodeFinding(**item))
            except Exception as e:
                logger.debug("Skipping malformed finding: %s — %s", item, e)
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse findings JSON: %s", e)
    return findings


def _compute_decision(findings: List[CodeFinding]) -> ReviewDecision:
    severity_order = {
        Severity.CRITICAL: 4,
        Severity.HIGH: 3,
        Severity.MEDIUM: 2,
        Severity.LOW: 1,
    }
    threshold = severity_order.get(
        Severity(settings.MIN_SEVERITY_TO_BLOCK), 3
    )
    for finding in findings:
        if severity_order.get(finding.severity, 0) >= threshold:
            return ReviewDecision.REQUEST_CHANGES
    if findings:
        return ReviewDecision.COMMENT
    return ReviewDecision.APPROVE


# ── Prompt Templates ──────────────────────────────────────────────────────────

_FINDINGS_FORMAT = """
Return a JSON array only, no markdown fences, no extra text. Each element:
{
  "severity": "LOW|MEDIUM|HIGH|CRITICAL",
  "file_path": "path/to/file.py",
  "line_number": 42,
  "title": "Short title",
  "description": "Detailed explanation",
  "suggestion": "How to fix it",
  "rule_id": "OPTIONAL_RULE_CODE"
}
"""

_SECURITY_SYSTEM = f"""You are an expert security code reviewer. Analyze the diff for:
- SQL injection, XSS, CSRF vulnerabilities
- Hardcoded secrets, API keys, passwords
- Insecure deserialization
- Path traversal, command injection
- Weak cryptography (MD5, SHA1 for passwords)
- Missing authentication/authorization
- Exposed debug endpoints
- Unsafe dependencies
{_FINDINGS_FORMAT}"""

_PERFORMANCE_SYSTEM = f"""You are an expert performance engineer. Analyze the diff for:
- N+1 database queries
- Missing database indexes (based on query patterns)
- Inefficient algorithms (O(n²) or worse where O(n) is possible)
- Memory leaks (unclosed resources, circular references)
- Blocking I/O in async code
- Unnecessary data fetching (SELECT *)
- Missing caching opportunities
- Expensive operations in loops
{_FINDINGS_FORMAT}"""

_STYLE_SYSTEM = f"""You are a senior software engineer focused on code quality. Analyze the diff for:
- PEP8 / language style guide violations
- Functions exceeding 50 lines / classes exceeding 200 lines
- Deep nesting (> 4 levels)
- Magic numbers / hardcoded strings
- Missing or inadequate docstrings
- Duplicate code (DRY violations)
- Poor variable/function naming
- Overly complex conditionals
- Missing type annotations (Python 3.9+)
{_FINDINGS_FORMAT}"""

_SUMMARY_SYSTEM = "You are a helpful code review assistant. Write concise, actionable PR review summaries."
_SUMMARY_HUMAN = """PR Title: {pr_title}
PR Description: {pr_body}
Review Decision: {decision}
Key Findings:
{findings}

Diff excerpt:
{diff}

Write a GitHub PR review comment. Be concise, professional, and constructive.
Start with an overall assessment, then highlight the most important issues.
Use emoji sparingly for visual clarity (✅ approve, ⚠️ warning, 🚨 critical)."""


def _security_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(_SECURITY_SYSTEM),
        HumanMessagePromptTemplate.from_template("Analyze this diff:\n\n{diff}"),
    ])


def _performance_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(_PERFORMANCE_SYSTEM),
        HumanMessagePromptTemplate.from_template("Analyze this diff:\n\n{diff}"),
    ])


def _style_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(_STYLE_SYSTEM),
        HumanMessagePromptTemplate.from_template("Analyze this diff:\n\n{diff}"),
    ])
