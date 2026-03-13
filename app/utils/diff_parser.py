"""
Diff Parser Utility — Extracts code context from unified diffs
"""
import re
from typing import Optional, Tuple


def extract_code_context(patch: str, target_line: int, context_lines: int = 3) -> Optional[str]:
    """
    Given a unified diff patch and a target line number (1-based),
    return the surrounding lines as a readable snippet.
    """
    if not patch:
        return None

    lines = patch.splitlines()
    current_line = 0
    collected = []

    for line in lines:
        hunk_match = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
        if hunk_match:
            current_line = int(hunk_match.group(1)) - 1
            continue

        if line.startswith("-"):
            continue  # deleted lines don't advance new line counter
        elif line.startswith("+"):
            current_line += 1
        else:
            current_line += 1

        if abs(current_line - target_line) <= context_lines:
            collected.append(line)

    return "\n".join(collected) if collected else None


def parse_hunk_header(hunk_header: str) -> Tuple[int, int, int, int]:
    """
    Parse a unified diff hunk header like '@@ -10,5 +12,8 @@'
    Returns (old_start, old_count, new_start, new_count).
    """
    match = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", hunk_header)
    if not match:
        return 0, 0, 0, 0
    old_start = int(match.group(1))
    old_count = int(match.group(2) or 1)
    new_start = int(match.group(3))
    new_count = int(match.group(4) or 1)
    return old_start, old_count, new_start, new_count


def count_diff_lines(patch: str) -> Tuple[int, int]:
    """Return (additions, deletions) count from a patch string."""
    additions = sum(1 for line in patch.splitlines() if line.startswith("+") and not line.startswith("+++"))
    deletions = sum(1 for line in patch.splitlines() if line.startswith("-") and not line.startswith("---"))
    return additions, deletions
