"""
Tests — Diff Parser Utility
"""
import pytest
from app.utils.diff_parser import count_diff_lines, extract_code_context, parse_hunk_header

SAMPLE_PATCH = """@@ -1,5 +1,7 @@
 import os
 import sys
+import hashlib
+import hmac
 
 def main():
-    pass
+    print("hello")
+    return 0
"""


def test_parse_hunk_header_standard():
    old_start, old_count, new_start, new_count = parse_hunk_header("@@ -1,5 +1,7 @@")
    assert old_start == 1
    assert old_count == 5
    assert new_start == 1
    assert new_count == 7


def test_parse_hunk_header_single_line():
    old_start, old_count, new_start, new_count = parse_hunk_header("@@ -10 +10,3 @@")
    assert old_start == 10
    assert old_count == 1
    assert new_start == 10
    assert new_count == 3


def test_parse_hunk_header_invalid():
    result = parse_hunk_header("not a hunk header")
    assert result == (0, 0, 0, 0)


def test_count_diff_lines():
    additions, deletions = count_diff_lines(SAMPLE_PATCH)
    assert additions == 4
    assert deletions == 1


def test_count_diff_lines_empty():
    assert count_diff_lines("") == (0, 0)


def test_extract_code_context_returns_snippet():
    snippet = extract_code_context(SAMPLE_PATCH, target_line=3, context_lines=2)
    assert snippet is not None
    assert len(snippet) > 0


def test_extract_code_context_empty_patch():
    result = extract_code_context("", target_line=5)
    assert result is None


def test_extract_code_context_out_of_range():
    result = extract_code_context(SAMPLE_PATCH, target_line=999, context_lines=2)
    # Should return empty or None — no lines near 999
    assert result is None or result == ""
