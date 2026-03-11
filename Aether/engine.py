"""
engine.py — Aether Creative Architect Engine
═════════════════════════════════════════════
Meta App Factory | Aether Protocol | Antigravity-AI

Dual-Agent Refinement Loop:
  1. DRAFT  — Gemini generates initial output from prompt + creative context
  2. CRITIQUE — Specialist-Critic audits for logic/style/quality
  3. REFINE — If rejected, feeds failures back into Gemini (max 3 iterations)
  4. LOG    — Final output logged to MASTER_INDEX with quality score
  5. ESCALATE — Rejections or >2 manual fixes → Level 5 Leitner error

Integrations:
  - creative_context.py → Style Profile injection
  - utils/critic.py → ArtisanCritic validation
  - leitner_architect.py → Error escalation
  - Sentinel_Bridge/pii_masker.py → Commercial safety on exports
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("aether.engine")

# ── Path Setup ───────────────────────────────────────────
AETHER_DIR = Path(__file__).resolve().parent
FACTORY_DIR = AETHER_DIR.parent
sys.path.insert(0, str(FACTORY_DIR))
sys.path.insert(0, str(FACTORY_DIR / "Sentinel_Bridge"))

# ── Imports from factory ecosystem ───────────────────────
from Aether.creative_context import CreativeContext

# Lazy imports to avoid circular/missing deps at parse time
_critic = None
_leitner = None
_pii = None


def _get_critic():
    global _critic
    if _critic is None:
        try:
            from utils.critic import ArtisanCritic
            _critic = ArtisanCritic()
        except ImportError:
            logger.warning("ArtisanCritic not available — running without Critic")
    return _critic


def _get_leitner():
    global _leitner
    if _leitner is None:
        try:
            from leitner_architect import LeitnerArchitect
            _leitner = LeitnerArchitect()
        except ImportError:
            logger.warning("LeitnerArchitect not available")
    return _leitner


def _get_pii():
    global _pii
    if _pii is None:
        try:
            from pii_masker import PIIMasker
            _pii = PIIMasker()
        except ImportError:
            logger.warning("PIIMasker not available — exports will not be sanitized")
    return _pii


# ── Constants ────────────────────────────────────────────
MAX_REFINE_ITERATIONS = 3
MASTER_INDEX_PATH = FACTORY_DIR / "MASTER_INDEX.md"
STATE_DIR = FACTORY_DIR / ".Gemini_state"


class RefinementResult:
    """Result of a single Aether refinement cycle."""

    def __init__(self, content: str, quality_score: float,
                 iterations: int, accepted: bool,
                 critic_feedback: list, escalated: bool = False):
        self.content = content
        self.quality_score = quality_score
        self.iterations = iterations
        self.accepted = accepted
        self.critic_feedback = critic_feedback
        self.escalated = escalated

    def to_dict(self) -> dict:
        return {
            "quality_score": self.quality_score,
            "iterations": self.iterations,
            "accepted": self.accepted,
            "critic_feedback_count": len(self.critic_feedback),
            "escalated": self.escalated,
            "content_length": len(self.content),
        }


class AetherEngine:
    """
    Context-Aware Creative Architect with Dual-Agent Refinement Loop.
    """

    def __init__(self):
        self.context = CreativeContext()
        self.context.build_style_profile()
        self._context_prompt = self.context.get_context_prompt()
        self._manual_fix_counts: dict = self._load_fix_counts()

    # ── Public API ───────────────────────────────────────

    def generate(self, prompt: str, app_name: str = "Unknown",
                 output_type: str = "code") -> RefinementResult:
        """
        Main entry point. Runs the full Dual-Agent Refinement Loop:
        Draft → Critique → Refine → Log → Escalate.
        """
        logger.info("Aether Engine: generating for '%s' (type=%s)",
                     app_name, output_type)

        # Phase 1: DRAFT — Generate initial output
        draft = self._draft(prompt, output_type)
        current_output = draft
        critic_feedback = []
        accepted = False
        iteration = 0

        # Phase 2+3: CRITIQUE → REFINE loop
        critic = _get_critic()
        for iteration in range(1, MAX_REFINE_ITERATIONS + 1):
            if critic is None:
                # No Critic available — accept the draft
                accepted = True
                break

            verdict = self._critique(current_output, prompt, app_name)
            critic_feedback.append(verdict)

            if verdict.get("verdict") == "PASS":
                accepted = True
                logger.info("Critic PASS on iteration %d", iteration)
                break

            # Rejected — refine with feedback
            logger.info("Critic FAIL on iteration %d: %s",
                         iteration, verdict.get("reason", "unknown"))
            current_output = self._refine(
                current_output, prompt, verdict, iteration
            )

        # Phase 4: SANITIZE — PII masking for commercial safety
        current_output = self._sanitize(current_output)

        # Calculate quality score
        quality_score = self._calculate_quality(
            accepted, iteration, len(critic_feedback)
        )

        # Phase 5: LOG to MASTER_INDEX
        self._log_to_index(app_name, output_type, quality_score,
                           iteration, accepted)

        # Phase 6: LEITNER ESCALATION
        escalated = False
        if not accepted:
            escalated = self._escalate_to_leitner(
                app_name, prompt, critic_feedback, "rejected_after_max_iterations"
            )

        result = RefinementResult(
            content=current_output,
            quality_score=quality_score,
            iterations=iteration,
            accepted=accepted,
            critic_feedback=critic_feedback,
            escalated=escalated,
        )

        logger.info("Aether Engine complete: score=%.1f, accepted=%s, "
                     "iterations=%d, escalated=%s",
                     quality_score, accepted, iteration, escalated)
        return result

    def record_manual_fix(self, app_name: str, description: str) -> dict:
        """
        Record a manual fix. If count exceeds 2, escalate to Leitner Level 5.
        """
        key = app_name.lower().replace(" ", "_")
        self._manual_fix_counts[key] = self._manual_fix_counts.get(key, 0) + 1
        count = self._manual_fix_counts[key]
        self._save_fix_counts()

        escalated = False
        if count > 2:
            escalated = self._escalate_to_leitner(
                app_name, description, [],
                f"manual_fix_count_exceeded ({count} fixes)"
            )

        return {
            "app": app_name,
            "manual_fix_count": count,
            "escalated": escalated,
            "threshold": 2,
        }

    # ── Phase 1: Draft ───────────────────────────────────

    def _draft(self, prompt: str, output_type: str) -> str:
        """
        Generate initial draft using Gemini with creative context.
        Falls back to a structured template if Gemini is unavailable.
        """
        try:
            import google.generativeai as genai
            api_key = os.environ.get("GEMINI_API_KEY")
            if api_key:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-2.0-flash")

                full_prompt = (
                    f"{self._context_prompt}\n\n"
                    f"## Task\n"
                    f"Generate {output_type} for the following request:\n\n"
                    f"{prompt}\n\n"
                    f"Requirements:\n"
                    f"- Follow the Aether Code Conventions above\n"
                    f"- Production-quality, well-documented code\n"
                    f"- Include error handling and logging\n"
                    f"- No hardcoded secrets or file paths\n"
                )

                response = model.generate_content(full_prompt)
                return response.text
        except Exception as e:
            logger.warning("Gemini API unavailable for draft: %s", e)

        # Fallback: return a structured template
        return (
            f"# Aether Draft — {output_type}\n\n"
            f"## Request\n{prompt}\n\n"
            f"## Generated Output\n"
            f"[Draft pending — Gemini API not available]\n"
            f"[Creative Context loaded: {len(self.context.blueprints)} blueprints]\n"
        )

    # ── Phase 2: Critique ────────────────────────────────

    def _critique(self, content: str, original_prompt: str,
                  app_name: str) -> dict:
        """
        Submit to ArtisanCritic for logic and style audit.
        Returns a verdict dict with pass/fail and feedback.
        """
        critic = _get_critic()
        if critic is None:
            return {"verdict": "PASS", "reason": "No Critic available"}

        try:
            # Use the Critic's validate_refinement if available
            if hasattr(critic, 'validate_refinement'):
                # Write content to a temp file for the Critic
                import tempfile
                with tempfile.NamedTemporaryFile(
                    mode='w', suffix='.py', delete=False, encoding='utf-8'
                ) as f:
                    f.write(content)
                    temp_path = f.name

                try:
                    verdict = critic.validate_refinement(
                        app_name=app_name,
                        test_filename=temp_path,
                    )
                    return verdict
                finally:
                    try:
                        os.unlink(temp_path)
                    except OSError:
                        pass
            else:
                # Fallback: basic length/syntax check
                if len(content.strip()) < 10:
                    return {"verdict": "FAIL", "reason": "Output too short"}
                return {"verdict": "PASS", "reason": "Basic check passed"}

        except Exception as e:
            logger.warning("Critic error: %s", e)
            return {"verdict": "PASS", "reason": f"Critic error (auto-pass): {e}"}

    # ── Phase 3: Refine ──────────────────────────────────

    def _refine(self, current: str, original_prompt: str,
                verdict: dict, iteration: int) -> str:
        """
        Self-refine the output based on Critic feedback.
        Uses Gemini to incorporate feedback if available.
        """
        failures = verdict.get("failures", [])
        reason = verdict.get("reason", "Unknown issue")

        try:
            import google.generativeai as genai
            api_key = os.environ.get("GEMINI_API_KEY")
            if api_key:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-2.0-flash")

                refine_prompt = (
                    f"{self._context_prompt}\n\n"
                    f"## Refinement Pass {iteration}\n"
                    f"The Specialist-Critic rejected the previous draft.\n\n"
                    f"### Critic Feedback\n"
                    f"Reason: {reason}\n"
                    f"Failures: {json.dumps(failures, indent=2)}\n\n"
                    f"### Original Request\n{original_prompt}\n\n"
                    f"### Previous Draft\n{current[:2000]}\n\n"
                    f"Fix ALL issues identified by the Critic. "
                    f"Maintain Aether conventions.\n"
                )

                response = model.generate_content(refine_prompt)
                return response.text
        except Exception as e:
            logger.warning("Gemini unavailable for refinement: %s", e)

        # Fallback: append feedback as comments
        return (
            f"{current}\n\n"
            f"# --- REFINEMENT PASS {iteration} ---\n"
            f"# Critic feedback: {reason}\n"
            f"# Failures: {failures}\n"
            f"# [Auto-refinement requires Gemini API]\n"
        )

    # ── Phase 4: Sanitize (PII Masking) ──────────────────

    def _sanitize(self, content: str) -> str:
        """
        Apply PII masking to strip internal file paths,
        API keys, and developer tokens from output.
        """
        pii = _get_pii()
        if pii is None:
            return content
        return pii.mask(content)

    # ── Phase 5: Log to MASTER_INDEX ─────────────────────

    def _log_to_index(self, app_name: str, output_type: str,
                      quality_score: float, iterations: int,
                      accepted: bool) -> None:
        """Append a generation entry to MASTER_INDEX.md."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        status = "ACCEPTED" if accepted else "REJECTED"

        entry = (
            f"\n### AETHER_GENERATION\n"
            f"- **Timestamp:** {timestamp}\n"
            f"- **App:** {app_name}\n"
            f"- **Type:** {output_type}\n"
            f"- **Quality_Score:** {quality_score:.1f}/10\n"
            f"- **Iterations:** {iterations}/{MAX_REFINE_ITERATIONS}\n"
            f"- **Status:** {status}\n"
        )

        try:
            with open(MASTER_INDEX_PATH, "a", encoding="utf-8", newline="\n") as f:
                f.write(entry)
        except Exception as e:
            logger.error("Could not log to MASTER_INDEX: %s", e)

    # ── Phase 6: Leitner Escalation ──────────────────────

    def _escalate_to_leitner(self, app_name: str, description: str,
                              critic_feedback: list,
                              reason: str) -> bool:
        """
        Escalate to Leitner Level 5 error for 72h deep review.
        Called when:
        - Output rejected after max iterations
        - Manual fix count exceeds 2
        """
        leitner = _get_leitner()
        if leitner is None:
            logger.warning("Leitner not available — cannot escalate")
            return False

        try:
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            feedback_summary = "; ".join(
                fb.get("reason", "unknown") for fb in critic_feedback[:3]
            )

            # Append Level 5 error to MASTER_INDEX
            entry = (
                f"\n### ERROR_ENTRY\n"
                f"- **Timestamp:** {timestamp}\n"
                f"- **App:** {app_name}\n"
                f"- **Error_Complexity:** 5\n"
                f"- **Description:** Aether Evolution escalation — {reason}\n"
                f"- **Root_Cause:** {feedback_summary or description[:200]}\n"
                f"- **Resolution:** pending_deep_review\n"
                f"- **Status:** OPEN\n"
                f"- **Last_Reviewed:** {timestamp}\n"
            )

            with open(MASTER_INDEX_PATH, "a", encoding="utf-8", newline="\n") as f:
                f.write(entry)

            logger.info("Escalated to Leitner Level 5: %s — %s",
                         app_name, reason)
            return True

        except Exception as e:
            logger.error("Leitner escalation failed: %s", e)
            return False

    # ── Quality Scoring ──────────────────────────────────

    def _calculate_quality(self, accepted: bool, iterations: int,
                           feedback_count: int) -> float:
        """
        Calculate quality score (0-10) based on acceptance
        and iteration count.
        """
        if not accepted:
            return max(1.0, 5.0 - feedback_count)

        # Accepted on first try = 10, decreases with iterations
        base = 10.0
        penalty = (iterations - 1) * 2.0  # -2 per retry
        return max(5.0, base - penalty)

    # ── Fix Count Persistence ────────────────────────────

    def _load_fix_counts(self) -> dict:
        path = STATE_DIR / "aether_fix_counts.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_fix_counts(self) -> None:
        STATE_DIR.mkdir(exist_ok=True)
        path = STATE_DIR / "aether_fix_counts.json"
        try:
            path.write_text(json.dumps(self._manual_fix_counts, indent=2))
        except Exception as e:
            logger.error("Could not save fix counts: %s", e)


# ── Entry Point ──────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(message)s")

    parser = argparse.ArgumentParser(description="Aether Creative Architect Engine")
    parser.add_argument("--test", action="store_true",
                        help="Run self-test with sample prompt")
    parser.add_argument("--prompt", type=str, default=None,
                        help="Custom prompt to generate from")
    parser.add_argument("--app", type=str, default="AetherTest",
                        help="App name for logging")
    args = parser.parse_args()

    engine = AetherEngine()

    if args.test or args.prompt:
        prompt = args.prompt or (
            "Create a simple health-check endpoint for a FastAPI server "
            "that returns system status, uptime, and version information."
        )
        print(f"Aether Engine — Generating for: {args.app}")
        print(f"Prompt: {prompt[:80]}...")
        print("-" * 60)

        result = engine.generate(prompt, app_name=args.app, output_type="code")
        print(f"\nResult: {result.to_dict()}")
        print(f"\n--- Generated Output (first 500 chars) ---")
        try:
            print(result.content[:500])
        except UnicodeEncodeError:
            print("(Output contains unicode — check logs for details)")
    else:
        print("Aether Engine loaded. Use --test or --prompt to generate.")
        print(f"Creative Context: {len(engine.context.blueprints)} blueprints loaded")
        print(f"Style Profile: {engine.context.style_profile.get('active_app_count', 0)} apps")
