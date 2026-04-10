"""
test_ast_correction.py — AST Correction Loop Validation
═══════════════════════════════════════════════════════════
Tests the UI-in-the-Loop validation pipeline:
  1. Lint detection: verifies Babel/heuristic catches broken JSX
  2. ESLint structural check: verifies function exists and handles missing ESLint
  3. Correction prompt construction: verifies the feedback prompt is well-formed
  4. Full pipeline simulation: injects broken JSX, confirms detection and prompt assembly

Does NOT call Gemini — tests the detection and feedback construction only.
"""

import os
import sys
import json
import tempfile
import shutil
from datetime import datetime

# Setup path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from refine_engine import (
    _lint_jsx_heuristic,
    _lint_jsx_node,
    _lint_file,
    _eslint_structural_check,
    _ast_correction_loop,
    AST_CORRECTION_PROMPT,
    parse_file_modifications,
)


def _create_temp_dir():
    """Create a temp directory for test files."""
    tmp = os.path.join(SCRIPT_DIR, ".ast_test_tmp")
    os.makedirs(tmp, exist_ok=True)
    return tmp


def _write_temp_file(tmp_dir, filename, content):
    """Write a file to the temp directory."""
    path = os.path.join(tmp_dir, filename)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    return path


# ── Test Cases ─────────────────────────────────────────────────

BROKEN_JSX_UNCLOSED_TAG = """
import React from 'react';

function App() {
    return (
        <div className="app">
            <h1>Hello World</h1>
            <p>This paragraph is missing a closing tag
            <span>Nested content</span>
        </div>
    );
}

export default App;
"""

BROKEN_JSX_COMMENT_IN_ATTR = """
import React from 'react';

function Button() {
    return (
        <button
            className="btn"
            {/* This comment is between attributes */}
            disabled={false}
        >
            Click me
        </button>
    );
}

export default Button;
"""

BROKEN_JSX_UNMATCHED_BRACES = """
import React, { useState } from 'react';

function Counter() {
    const [count, setCount] = useState(0);
    return (
        <div>
            <p>Count: {count</p>
            <button onClick={() => setCount(count + 1)}>+</button>
        </div>
    );
}

export default Counter;
"""

BROKEN_JSX_UNCLOSED_TEMPLATE = """
import React from 'react';

function Greeting({ name }) {
    const message = `Hello, ${name}! Welcome to our app;
    return (
        <div>
            <h1>{message}</h1>
        </div>
    );
}

export default Greeting;
"""

VALID_JSX = """
import React, { useState } from 'react';

function App() {
    const [count, setCount] = useState(0);
    return (
        <div className="app">
            <h1>Counter: {count}</h1>
            <button onClick={() => setCount(count + 1)}>Increment</button>
        </div>
    );
}

export default App;
"""


def main():
    print(f"\n{'═'*60}")
    print(f"  🧪 AST CORRECTION LOOP — Test Suite")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'═'*60}\n")

    tmp_dir = _create_temp_dir()
    passed = 0
    failed = 0
    total = 0

    def check(name, condition):
        nonlocal passed, failed, total
        total += 1
        if condition:
            passed += 1
            print(f"  ✅ PASS: {name}")
        else:
            failed += 1
            print(f"  ❌ FAIL: {name}")

    try:
        # ─────────────────────────────────────────────────────
        print(f"\n{'─'*55}")
        print(f"  TEST 1: Heuristic catches unclosed tag")
        print(f"{'─'*55}")
        
        f1 = _write_temp_file(tmp_dir, "UnclosedTag.jsx", BROKEN_JSX_UNCLOSED_TAG)
        errors = _lint_jsx_heuristic(f1, "UnclosedTag.jsx")
        check("Errors detected for unclosed tag", len(errors) > 0)
        for e in errors:
            print(f"    → {e}")

        # ─────────────────────────────────────────────────────
        print(f"\n{'─'*55}")
        print(f"  TEST 2: Heuristic catches JSX comment in attribute list")
        print(f"{'─'*55}")

        f2 = _write_temp_file(tmp_dir, "CommentInAttr.jsx", BROKEN_JSX_COMMENT_IN_ATTR)
        errors = _lint_jsx_heuristic(f2, "CommentInAttr.jsx")
        check("Errors detected for comment in attributes", len(errors) > 0)
        has_attr_comment_error = any("comment" in e.lower() and "attribute" in e.lower() for e in errors)
        check("Error message mentions 'comment' and 'attribute'", has_attr_comment_error)
        for e in errors:
            print(f"    → {e}")

        # ─────────────────────────────────────────────────────
        print(f"\n{'─'*55}")
        print(f"  TEST 3: Heuristic catches unmatched braces")
        print(f"{'─'*55}")

        f3 = _write_temp_file(tmp_dir, "UnmatchedBraces.jsx", BROKEN_JSX_UNMATCHED_BRACES)
        errors = _lint_jsx_heuristic(f3, "UnmatchedBraces.jsx")
        check("Errors detected for unmatched braces", len(errors) > 0)
        for e in errors:
            print(f"    → {e}")

        # ─────────────────────────────────────────────────────
        print(f"\n{'─'*55}")
        print(f"  TEST 4: Heuristic catches unclosed template literal")
        print(f"{'─'*55}")

        f4 = _write_temp_file(tmp_dir, "UnclosedTemplate.jsx", BROKEN_JSX_UNCLOSED_TEMPLATE)
        errors = _lint_jsx_heuristic(f4, "UnclosedTemplate.jsx")
        check("Errors detected for unclosed template literal", len(errors) > 0)
        has_backtick_error = any("backtick" in e.lower() or "template" in e.lower() for e in errors)
        check("Error message mentions 'backtick' or 'template'", has_backtick_error)
        for e in errors:
            print(f"    → {e}")

        # ─────────────────────────────────────────────────────
        print(f"\n{'─'*55}")
        print(f"  TEST 5: Valid JSX passes heuristic lint cleanly")
        print(f"{'─'*55}")

        f5 = _write_temp_file(tmp_dir, "ValidApp.jsx", VALID_JSX)
        errors = _lint_jsx_heuristic(f5, "ValidApp.jsx")
        check("No errors for valid JSX", len(errors) == 0)

        # ─────────────────────────────────────────────────────
        print(f"\n{'─'*55}")
        print(f"  TEST 6: _lint_file dispatcher routes JSX correctly")
        print(f"{'─'*55}")

        errors = _lint_file(f3, "UnmatchedBraces.jsx", tmp_dir)
        check("_lint_file returns errors for broken JSX", len(errors) > 0)

        errors_valid = _lint_file(f5, "ValidApp.jsx", tmp_dir)
        check("_lint_file returns [] for valid JSX", len(errors_valid) == 0)

        # ─────────────────────────────────────────────────────
        print(f"\n{'─'*55}")
        print(f"  TEST 7: ESLint structural check handles missing ESLint gracefully")
        print(f"{'─'*55}")

        # Since tmp_dir has no node_modules, ESLint should return []
        result = _eslint_structural_check(f3, "UnmatchedBraces.jsx", tmp_dir)
        check("ESLint returns [] when not installed (graceful fallback)", result == [])

        # ─────────────────────────────────────────────────────
        print(f"\n{'─'*55}")
        print(f"  TEST 8: AST Correction prompt is well-formed")
        print(f"{'─'*55}")

        sample_errors = [
            "App.jsx:8: PARSE_ERROR: Unexpected token (8:13)",
            "App.jsx: Unclosed brackets — 1 unmatched opening bracket(s)",
        ]
        sample_eslint = [
            "App.jsx:3:7: [WARN] 'unused' is defined but never used (no-unused-vars)",
        ]

        lines = BROKEN_JSX_UNMATCHED_BRACES.strip().split("\n")
        numbered = "\n".join(f"{i+1:4d} | {line}" for i, line in enumerate(lines))

        prompt = AST_CORRECTION_PROMPT.format(
            errors="\n".join(f"  - {e}" for e in sample_errors),
            eslint_issues="\n".join(f"  - {e}" for e in sample_eslint),
            rel_path="src/App.jsx",
            numbered_code=numbered,
        )

        check("Prompt contains BABEL PARSE ERRORS section", "BABEL PARSE ERRORS" in prompt)
        check("Prompt contains ESLINT STRUCTURAL ISSUES section", "ESLINT STRUCTURAL ISSUES" in prompt)
        check("Prompt contains numbered code", "   1 |" in prompt)
        check("Prompt contains rel_path", "src/App.jsx" in prompt)
        check("Prompt contains correction rules", "NEVER place JSX comments" in prompt)
        check("Prompt contains ===FILE: format instruction", "===FILE: src/App.jsx===" in prompt)
        check("Prompt length is reasonable (<10k chars)", len(prompt) < 10000)
        print(f"    → Prompt length: {len(prompt)} chars")

        # ─────────────────────────────────────────────────────
        print(f"\n{'─'*55}")
        print(f"  TEST 9: parse_file_modifications extracts corrected code")
        print(f"{'─'*55}")

        mock_response = """Here are the corrections:

===FILE: src/App.jsx===
import React, { useState } from 'react';

function Counter() {
    const [count, setCount] = useState(0);
    return (
        <div>
            <p>Count: {count}</p>
            <button onClick={() => setCount(count + 1)}>+</button>
        </div>
    );
}

export default Counter;
===END_FILE===
"""
        mods = parse_file_modifications(mock_response)
        check("Extracted 1 file from mock response", len(mods) == 1)
        check("Correct path extracted", "src/App.jsx" in mods)
        if "src/App.jsx" in mods:
            check("Corrected code contains fixed JSX", "{count}</p>" in mods["src/App.jsx"])
            check("Corrected code is complete", "export default Counter" in mods["src/App.jsx"])

        # ─────────────────────────────────────────────────────
        print(f"\n{'─'*55}")
        print(f"  TEST 10: Python lint check (control)")
        print(f"{'─'*55}")

        py_valid = _write_temp_file(tmp_dir, "valid.py", "def hello():\n    return 'world'\n")
        py_broken = _write_temp_file(tmp_dir, "broken.py", "def hello(\n    return 'world'\n")

        errors_ok = _lint_file(py_valid, "valid.py", tmp_dir)
        check("Valid Python passes lint", len(errors_ok) == 0)

        errors_bad = _lint_file(py_broken, "broken.py", tmp_dir)
        check("Broken Python caught by lint", len(errors_bad) > 0)
        for e in errors_bad:
            print(f"    → {e}")

    finally:
        # Cleanup
        try:
            shutil.rmtree(tmp_dir)
        except Exception:
            pass

    # ─────────────────────────────────────────────────────
    print(f"\n{'═'*60}")
    print(f"  🏁 TEST RESULTS: {passed} passed, {failed} failed")
    if failed == 0:
        print(f"  ✅ ALL TESTS PASSED")
    else:
        print(f"  ❌ {failed} TEST(S) FAILED")
    print(f"{'═'*60}\n")

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
