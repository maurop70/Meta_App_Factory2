"""
brand_guardian.py — Brand Identity Enforcer (Aether)
══════════════════════════════════════════════════════
Project_Aether | Antigravity V3.0 | Venture Studio Phase 1

Enforces the Project Soul's brand identity (fonts, colors, mission)
across ALL generated files. Scans outputs for compliance and produces
a Brand Compliance Score.

Architecture:
    1. Load brand_identity.json from any project's soul/
    2. Validate generated files (HTML, CSS, JSON, DOCX metadata)
    3. Produce a compliance report with actionable violations
    4. Auto-inject brand tokens into new files when possible

Usage:
    from brand_guardian import BrandGuardian
    guardian = BrandGuardian("projects/Project_Alpha/soul/brand_identity.json")
    report = guardian.audit_file("output.html")
    guardian.enforce("output.html")
"""

import os
import sys
import re
import json
import logging
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FACTORY_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, ".."))
sys.path.insert(0, FACTORY_DIR)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logger = logging.getLogger("aether.brand_guardian")


class BrandGuardian:
    """
    Enforces brand consistency across all generated assets.

    Features:
        - Color palette validation (hex match check)
        - Font family enforcement
        - Mission/tagline presence
        - Visual style scoring
        - Auto-injection of brand CSS variables
    """

    def __init__(self, brand_file=None, project_dir=None):
        """
        Load brand identity from file or project directory.
        """
        self.brand = {}
        self.brand_file = brand_file

        if brand_file and os.path.exists(brand_file):
            self._load(brand_file)
        elif project_dir:
            soul_path = os.path.join(project_dir, "soul", "brand_identity.json")
            if os.path.exists(soul_path):
                self._load(soul_path)
                self.brand_file = soul_path

        logger.info("BrandGuardian initialized for: %s",
                     self.brand.get("company_name", "Unknown"))

    def _load(self, path):
        """Load brand_identity.json."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.brand = json.load(f)
        except Exception as e:
            logger.error("Failed to load brand file: %s", e)
            self.brand = {}

    # ── Accessors ────────────────────────────────────────

    @property
    def colors(self):
        return self.brand.get("colors", {})

    @property
    def fonts(self):
        return self.brand.get("fonts", {})

    @property
    def mission(self):
        return self.brand.get("mission", "")

    @property
    def company_name(self):
        return self.brand.get("company_name", "")

    @property
    def tone(self):
        return self.brand.get("tone_of_voice", "")

    # ── Audit Engine ─────────────────────────────────────

    def audit_file(self, file_path):
        """
        Audit a generated file for brand compliance.
        Returns a BrandReport dict with score and violations.
        """
        if not os.path.exists(file_path):
            return self._report(file_path, 0, ["File not found"])

        ext = os.path.splitext(file_path)[1].lower()

        if ext in (".html", ".htm"):
            return self._audit_html(file_path)
        elif ext == ".css":
            return self._audit_css(file_path)
        elif ext == ".json":
            return self._audit_json(file_path)
        else:
            return self._audit_text(file_path)

    def audit_directory(self, directory, extensions=None):
        """
        Audit all files in a directory. Returns aggregated report.
        """
        if extensions is None:
            extensions = [".html", ".htm", ".css", ".json", ".txt"]

        reports = []
        for root, dirs, files in os.walk(directory):
            for fname in files:
                if any(fname.endswith(ext) for ext in extensions):
                    fpath = os.path.join(root, fname)
                    report = self.audit_file(fpath)
                    reports.append(report)

        if not reports:
            return {
                "directory": directory,
                "files_scanned": 0,
                "overall_score": 100,
                "details": [],
            }

        avg_score = sum(r["score"] for r in reports) / len(reports)
        return {
            "directory": directory,
            "files_scanned": len(reports),
            "overall_score": round(avg_score, 1),
            "passing": sum(1 for r in reports if r["score"] >= 70),
            "failing": sum(1 for r in reports if r["score"] < 70),
            "details": reports,
            "audited_at": datetime.now().isoformat(),
        }

    # ── Enforcement ──────────────────────────────────────

    def enforce(self, file_path):
        """
        Auto-inject brand tokens into a file.
        Currently supports HTML/CSS injection.
        """
        if not os.path.exists(file_path):
            return {"status": "error", "message": "File not found"}

        ext = os.path.splitext(file_path)[1].lower()

        if ext in (".html", ".htm"):
            return self._enforce_html(file_path)
        elif ext == ".css":
            return self._enforce_css(file_path)
        else:
            return {"status": "skipped", "message": f"No enforcer for {ext}"}

    def get_css_variables(self):
        """Generate CSS custom properties from brand identity."""
        colors = self.colors
        fonts = self.fonts

        lines = [":root {"]
        for name, value in colors.items():
            css_name = name.replace("_", "-")
            lines.append(f"  --brand-{css_name}: {value};")
        for name, value in fonts.items():
            css_name = name.replace("_", "-")
            lines.append(f"  --brand-font-{css_name}: '{value}', sans-serif;")
        lines.append("}")
        return "\n".join(lines)

    def get_meta_tags(self):
        """Generate HTML meta tags from brand identity."""
        tags = []
        if self.company_name:
            tags.append(f'<meta name="author" content="{self.company_name}">')
        if self.mission:
            tags.append(f'<meta name="description" content="{self.mission}">')
        if self.tone:
            tags.append(f'<meta name="tone" content="{self.tone}">')
        return "\n".join(tags)

    # ── Private Auditors ─────────────────────────────────

    def _audit_html(self, path):
        """Audit an HTML file for brand compliance."""
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        violations = []
        score = 100

        # Check colors
        brand_colors = list(self.colors.values())
        if brand_colors:
            found_colors = re.findall(r'#[0-9a-fA-F]{6}', content)
            brand_found = sum(1 for c in found_colors if c.lower() in [bc.lower() for bc in brand_colors])
            if found_colors and brand_found == 0:
                violations.append(f"No brand colors found (expected: {', '.join(brand_colors[:3])})")
                score -= 15
            elif found_colors:
                ratio = brand_found / len(found_colors)
                if ratio < 0.3:
                    violations.append(f"Low brand color usage: {brand_found}/{len(found_colors)} ({ratio:.0%})")
                    score -= 10

        # Check fonts
        brand_fonts = list(self.fonts.values())
        for font in brand_fonts:
            if font and font.lower() not in content.lower():
                violations.append(f"Missing brand font: '{font}'")
                score -= 5

        # Check company name
        if self.company_name and self.company_name.lower() not in content.lower():
            violations.append(f"Company name '{self.company_name}' not found")
            score -= 10

        # Check mission statement
        if self.mission and len(self.mission) > 5:
            # Check for partial match (first 30 chars of mission)
            mission_preview = self.mission[:30].lower()
            if mission_preview not in content.lower():
                violations.append("Mission statement not present")
                score -= 5

        # Check meta tags
        if "<meta" not in content:
            violations.append("No meta tags found")
            score -= 5

        return self._report(path, max(0, score), violations)

    def _audit_css(self, path):
        """Audit a CSS file for brand compliance."""
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        violations = []
        score = 100

        # Check brand colors
        for color_name, color_val in self.colors.items():
            if color_val.lower() not in content.lower():
                violations.append(f"Brand color '{color_name}' ({color_val}) not used")
                score -= 8

        # Check font families
        for font_role, font_name in self.fonts.items():
            if font_name and font_name.lower() not in content.lower():
                violations.append(f"Brand font '{font_name}' ({font_role}) not declared")
                score -= 5

        # Check CSS variables
        if "--brand-" not in content:
            violations.append("No --brand-* CSS custom properties found")
            score -= 10

        return self._report(path, max(0, score), violations)

    def _audit_json(self, path):
        """Audit a JSON config for brand references."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            content = json.dumps(data)
        except Exception:
            return self._report(path, 50, ["Invalid JSON"])

        violations = []
        score = 100

        if self.company_name and self.company_name.lower() not in content.lower():
            violations.append("Company name not referenced")
            score -= 15

        return self._report(path, max(0, score), violations)

    def _audit_text(self, path):
        """Audit a generic text file."""
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception:
            return self._report(path, 0, ["Cannot read file"])

        violations = []
        score = 100

        if self.company_name and self.company_name.lower() not in content.lower():
            violations.append("Company name not found")
            score -= 20

        return self._report(path, max(0, score), violations)

    # ── Private Enforcers ────────────────────────────────

    def _enforce_html(self, path):
        """Inject brand CSS variables and meta tags into HTML."""
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        changes = 0

        # Inject CSS variables into <head>
        css_vars = self.get_css_variables()
        if "--brand-" not in content and "<head>" in content:
            style_block = f"\n<style>\n/* Brand Guardian — Auto-Injected */\n{css_vars}\n</style>\n"
            content = content.replace("<head>", f"<head>{style_block}", 1)
            changes += 1

        # Inject meta tags
        meta_tags = self.get_meta_tags()
        if meta_tags and '<meta name="author"' not in content and "<head>" in content:
            content = content.replace("<head>", f"<head>\n{meta_tags}\n", 1)
            changes += 1

        # Inject Google Fonts link for brand fonts
        brand_fonts = self.fonts
        for font_role, font_name in brand_fonts.items():
            if font_name and font_name not in content and "fonts.googleapis.com" not in content:
                font_link = f'<link href="https://fonts.googleapis.com/css2?family={font_name.replace(" ", "+")}:wght@300;400;500;600;700&display=swap" rel="stylesheet">'
                content = content.replace("<head>", f"<head>\n{font_link}", 1)
                changes += 1
                break  # Only inject once

        if changes > 0:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

        return {
            "status": "enforced" if changes > 0 else "no_changes",
            "changes": changes,
            "file": path,
        }

    def _enforce_css(self, path):
        """Prepend brand CSS variables to a CSS file."""
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        if "--brand-" in content:
            return {"status": "no_changes", "file": path}

        css_vars = self.get_css_variables()
        header = f"/* Brand Guardian — Auto-Injected ({datetime.now().strftime('%Y-%m-%d')}) */\n{css_vars}\n\n"
        content = header + content

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        return {"status": "enforced", "changes": 1, "file": path}

    # ── Report Builder ───────────────────────────────────

    def _report(self, file_path, score, violations):
        """Build a compliance report dict."""
        return {
            "file": os.path.basename(file_path),
            "path": file_path,
            "score": score,
            "grade": self._grade(score),
            "violations": violations,
            "compliant": score >= 70,
            "brand": self.company_name,
            "audited_at": datetime.now().isoformat(),
        }

    @staticmethod
    def _grade(score):
        """Convert score to letter grade."""
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        return "F"


# ── CLI ──────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Brand Guardian — Aether Brand Enforcer")
    parser.add_argument("--brand", required=True, help="Path to brand_identity.json")
    parser.add_argument("--audit", help="File or directory to audit")
    parser.add_argument("--enforce", help="File to enforce brand on")
    parser.add_argument("--generate-css", action="store_true", help="Print brand CSS variables")
    args = parser.parse_args()

    guardian = BrandGuardian(brand_file=args.brand)
    print(f"\n{'='*55}")
    print(f"  🛡️ Brand Guardian — {guardian.company_name}")
    print(f"{'='*55}\n")

    if args.generate_css:
        print(guardian.get_css_variables())

    if args.audit:
        if os.path.isdir(args.audit):
            report = guardian.audit_directory(args.audit)
            print(f"  📊 Directory Audit: {report['files_scanned']} files")
            print(f"     Overall Score: {report['overall_score']}/100")
            print(f"     Passing: {report['passing']}, Failing: {report['failing']}")
            for detail in report["details"]:
                icon = "✅" if detail["compliant"] else "❌"
                print(f"     {icon} {detail['file']}: {detail['score']}/100 ({detail['grade']})")
                for v in detail["violations"]:
                    print(f"        ⚠️  {v}")
        else:
            report = guardian.audit_file(args.audit)
            icon = "✅" if report["compliant"] else "❌"
            print(f"  {icon} {report['file']}: {report['score']}/100 ({report['grade']})")
            for v in report["violations"]:
                print(f"     ⚠️  {v}")

    if args.enforce:
        result = guardian.enforce(args.enforce)
        print(f"\n  Enforcement: {result['status']} ({result.get('changes', 0)} changes)")

    print(f"\n{'='*55}\n")
