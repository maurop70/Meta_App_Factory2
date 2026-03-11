"""
jsx_validator.py -- JSX/React Syntax Validation Hook
======================================================
Meta App Factory | utils | Antigravity-AI

Pre-deploy validation hook that catches common JSX/React syntax errors
before they break charts and dashboards. Resolves the Level 4 JSX parse
error from MASTER_INDEX.md.

Usage:
    from utils.jsx_validator import JSXValidator
    v = JSXValidator()
    result = v.validate_file("path/to/Component.jsx")
"""

import os
import re
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("factory.jsx_validator")


# ── Common JSX Error Patterns ────────────────────────────

JSX_ERROR_PATTERNS = [
    {
        "id": "COMMENT_IN_ATTRS",
        "pattern": r'<\w+[^>]*\{/\*.*?\*/\}[^>]*>',
        "description": "JSX comment {/* */} placed between tag attributes",
        "severity": "critical",
        "fix": "Move comments outside of JSX tag attribute lists",
    },
    {
        "id": "UNCLOSED_TAG",
        "pattern": r'<(\w+)(?:\s[^>]*)?(?<!/)>\s*$',
        "description": "Potentially unclosed JSX tag",
        "severity": "warning",
        "fix": "Ensure all opening tags have matching closing tags or use self-closing syntax",
    },
    {
        "id": "UNCLOSED_EXPRESSION",
        "pattern": r'\{[^}]*$',
        "description": "Unclosed JSX expression brace",
        "severity": "critical",
        "fix": "Close all { brackets with matching }",
    },
    {
        "id": "INVALID_ATTR_QUOTE",
        "pattern": r'=\s*"[^"]*\'|=\s*\'[^\']*"',
        "description": "Mixed quotes in JSX attribute",
        "severity": "warning",
        "fix": "Use consistent quoting (double quotes preferred in JSX)",
    },
    {
        "id": "CLASSNAME_TYPO",
        "pattern": r'\bclass\s*=',
        "description": "Using 'class' instead of 'className' in JSX",
        "severity": "critical",
        "fix": "Replace 'class=' with 'className=' in JSX",
    },
    {
        "id": "FOR_TYPO",
        "pattern": r'\bfor\s*=\s*["\']',
        "description": "Using 'for' instead of 'htmlFor' in JSX",
        "severity": "warning",
        "fix": "Replace 'for=' with 'htmlFor=' in JSX label elements",
    },
    {
        "id": "DANGLING_COMMA_IMPORT",
        "pattern": r'import\s+\{[^}]*,\s*\}',
        "description": "Dangling comma in import statement",
        "severity": "info",
        "fix": "Remove trailing comma in import destructuring (optional)",
    },
]


class JSXValidationResult:
    """Result of a JSX validation check."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.issues: list = []
        self.lines_scanned = 0

    @property
    def passed(self) -> bool:
        return not any(i["severity"] == "critical" for i in self.issues)

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i["severity"] == "critical")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i["severity"] == "warning")

    def to_dict(self) -> dict:
        return {
            "file": os.path.basename(self.file_path),
            "passed": self.passed,
            "lines_scanned": self.lines_scanned,
            "critical": self.critical_count,
            "warnings": self.warning_count,
            "issues": self.issues[:20],  # cap at 20
        }


class JSXValidator:
    """
    Pre-deploy JSX/React syntax validation hook.
    Catches common errors that cause Babel parse failures.
    """

    def __init__(self, patterns: list = None):
        self._patterns = patterns or JSX_ERROR_PATTERNS

    # ── Validate File ────────────────────────────────────

    def validate_file(self, file_path: str) -> JSXValidationResult:
        """Validate a single JSX/JS/TSX file."""
        result = JSXValidationResult(file_path)

        if not os.path.exists(file_path):
            result.issues.append({
                "line": 0,
                "severity": "critical",
                "id": "FILE_NOT_FOUND",
                "description": f"File not found: {file_path}",
                "fix": "Check file path",
            })
            return result

        try:
            content = Path(file_path).read_text(encoding="utf-8")
        except Exception as e:
            result.issues.append({
                "line": 0,
                "severity": "critical",
                "id": "READ_ERROR",
                "description": f"Cannot read file: {e}",
                "fix": "Check file encoding and permissions",
            })
            return result

        lines = content.split("\n")
        result.lines_scanned = len(lines)

        # Check each pattern against the full content first
        for pattern_def in self._patterns:
            matches = re.finditer(
                pattern_def["pattern"], content, re.MULTILINE
            )
            for match in matches:
                # Find the line number
                line_num = content[:match.start()].count("\n") + 1
                result.issues.append({
                    "line": line_num,
                    "severity": pattern_def["severity"],
                    "id": pattern_def["id"],
                    "description": pattern_def["description"],
                    "fix": pattern_def["fix"],
                    "match": match.group()[:80],
                })

        # Bracket balance check
        self._check_brackets(content, result)

        return result

    # ── Validate Directory ───────────────────────────────

    def validate_directory(self, dir_path: str,
                           extensions: tuple = (".jsx", ".tsx", ".js")
                           ) -> dict:
        """Validate all JSX/JS files in a directory tree."""
        results = []
        total_issues = 0

        for root, _, files in os.walk(dir_path):
            # Skip node_modules and build dirs
            if "node_modules" in root or "dist" in root or "build" in root:
                continue
            for fname in files:
                if fname.endswith(extensions):
                    fpath = os.path.join(root, fname)
                    r = self.validate_file(fpath)
                    if r.issues:
                        results.append(r.to_dict())
                        total_issues += len(r.issues)

        return {
            "files_with_issues": len(results),
            "total_issues": total_issues,
            "results": results,
        }

    # ── Bracket Balance ──────────────────────────────────

    def _check_brackets(self, content: str,
                        result: JSXValidationResult) -> None:
        """Check for unbalanced brackets in JSX."""
        pairs = {"(": ")", "{": "}", "[": "]", "<": ">"}
        # Only check curly and round brackets (< > are too noisy in JSX)
        check = {"(": 0, "{": 0, "[": 0}

        for i, char in enumerate(content):
            if char in check:
                check[char] += 1
            elif char == ")":
                check["("] -= 1
            elif char == "}":
                check["{"] -= 1
            elif char == "]":
                check["["] -= 1

        for bracket, count in check.items():
            if count != 0:
                closer = pairs[bracket]
                direction = "unclosed" if count > 0 else "extra closing"
                result.issues.append({
                    "line": 0,
                    "severity": "warning",
                    "id": "BRACKET_IMBALANCE",
                    "description": (
                        f"{abs(count)} {direction} '{bracket}{closer}' "
                        f"bracket(s) in file"
                    ),
                    "fix": f"Check {bracket}{closer} bracket balance",
                })


# ── Entry Point ──────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(message)s")

    parser = argparse.ArgumentParser(
        description="JSX/React Syntax Validator"
    )
    parser.add_argument("--test", action="store_true",
                        help="Run self-test with sample JSX")
    parser.add_argument("--scan", type=str,
                        help="Scan a directory for JSX issues")
    args = parser.parse_args()

    validator = JSXValidator()

    if args.test:
        print("JSX Validator -- Self-Test")
        print("-" * 50)

        # Create a temp test file with known issues
        import tempfile
        test_jsx = '''
import React from 'react';
import { useState, } from 'react';

function BadComponent() {
    return (
        <div class="container">
            <label for="name">Name</label>
            <input id="name" />
        </div>
    );
}

export default BadComponent;
'''
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsx", delete=False, encoding="utf-8"
        ) as f:
            f.write(test_jsx)
            tmp_path = f.name

        result = validator.validate_file(tmp_path)
        print(f"File: {result.file_path}")
        print(f"Passed: {result.passed}")
        print(f"Lines: {result.lines_scanned}")
        print(f"Critical: {result.critical_count}")
        print(f"Warnings: {result.warning_count}")

        for issue in result.issues:
            icon = {"critical": "X", "warning": "!", "info": "i"}.get(
                issue["severity"], "?"
            )
            print(f"  [{icon}] L{issue['line']}: {issue['description']}")
            print(f"      Fix: {issue['fix']}")

        os.unlink(tmp_path)
        print("\nSelf-test complete!")

    elif args.scan:
        print(f"Scanning: {args.scan}")
        report = validator.validate_directory(args.scan)
        print(f"Files with issues: {report['files_with_issues']}")
        print(f"Total issues: {report['total_issues']}")
        for r in report["results"]:
            print(f"\n  {r['file']}: {r['critical']} critical, "
                  f"{r['warnings']} warnings")
            for issue in r["issues"][:5]:
                print(f"    L{issue['line']}: {issue['description']}")

    else:
        print("Use --test for self-test or --scan <dir> to scan JSX files.")
