"""
warroom_outcomes.py — Prediction Ledger & Reality Reconciliation
═════════════════════════════════════════════════════════════════════════
Closes the War Room's accountability loop (Flaw #4): every consensus-
approved plan's quantitative claims become tracked predictions; actuals
are recorded as they materialize; per-agent calibration is computed from
the reconciled record and injected back into the next debate.

Flow:
    CONSENSUS REACHED → capture_from_reports() snapshots the typed
    handoff metrics into Boardroom_Exchange/predictions/{project}.json
    → record_actual() reconciles a metric against reality, computes the
    signed error and fires a tripwire if tolerance is breached
    → agent_calibration() aggregates errors across all projects
    → calibration_prompt_block() turns that record into prompt context
    → reference_class() gives the Critic base rates across past plans.

Storage layout:
    Project_Aether/Boardroom_Exchange/predictions/{project_id}.json
    Project_Aether/Boardroom_Exchange/predictions/tripwire_alerts.json
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from warroom_protocol import BOARDROOM_DIR

logger = logging.getLogger("WarRoom.Outcomes")

PREDICTIONS_DIR = os.path.join(BOARDROOM_DIR, "predictions")
TRIPWIRE_ALERTS_PATH = os.path.join(PREDICTIONS_DIR, "tripwire_alerts.json")

# ── Tracked metrics ───────────────────────────────────────────────────
# (agent, handoff field) → unit, violation direction, tripwire tolerance %.
# direction "over_is_bad": reality exceeding the prediction violates the
# plan (costs, timelines). "under_is_bad": reality falling short violates
# it (revenue, ROI).
TRACKED_METRICS: Dict[str, List[Dict[str, Any]]] = {
    "CMO": [
        {"metric": "marketing_cost",               "unit": "$",      "direction": "over_is_bad",  "tolerance_pct": 30.0},
        {"metric": "projected_revenue",            "unit": "$",      "direction": "under_is_bad", "tolerance_pct": 40.0},
        {"metric": "cost_per_acquisition",         "unit": "$",      "direction": "over_is_bad",  "tolerance_pct": 50.0},
        {"metric": "revenue_timeline_months",      "unit": "months", "direction": "over_is_bad",  "tolerance_pct": 50.0},
    ],
    "CTO": [
        {"metric": "implementation_timeline_weeks", "unit": "weeks", "direction": "over_is_bad",  "tolerance_pct": 40.0},
        {"metric": "infrastructure_cost_estimate",  "unit": "$/mo",  "direction": "over_is_bad",  "tolerance_pct": 50.0},
    ],
    "CFO": [
        {"metric": "roi_percentage",   "unit": "%",    "direction": "under_is_bad", "tolerance_pct": 50.0},
        {"metric": "breakeven_month",  "unit": "month","direction": "over_is_bad",  "tolerance_pct": 50.0},
        {"metric": "burn_rate",        "unit": "$/mo", "direction": "over_is_bad",  "tolerance_pct": 40.0},
        {"metric": "funding_required", "unit": "$",    "direction": "over_is_bad",  "tolerance_pct": 30.0},
    ],
}


class Prediction(BaseModel):
    prediction_id: str
    project_id: str
    agent: str
    metric: str
    predicted: float
    unit: str = ""
    direction: str = "over_is_bad"
    tolerance_pct: float = 30.0
    iteration: int = 1
    captured_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # ── Reconciliation (filled when reality arrives) ──
    actual: Optional[float] = None
    recorded_at: Optional[str] = None
    source: Optional[str] = None
    error_pct: Optional[float] = None     # signed: (actual - predicted) / predicted * 100
    tripwire_fired: bool = False


class PredictionLedger:
    """File-backed ledger of plan predictions and their reconciliation."""

    def __init__(self, base_dir: str = None):
        self.base_dir = base_dir or PREDICTIONS_DIR
        self.alerts_path = os.path.join(self.base_dir, "tripwire_alerts.json")
        os.makedirs(self.base_dir, exist_ok=True)

    def _path(self, project_id: str) -> str:
        safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in project_id)
        return os.path.join(self.base_dir, f"{safe}.json")

    def _load(self, project_id: str) -> List[Prediction]:
        path = self._path(project_id)
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [Prediction(**p) for p in data.get("predictions", [])]
        except Exception as e:
            logger.warning(f"[Ledger] Failed to load {path}: {e}")
            return []

    def _save(self, project_id: str, predictions: List[Prediction]):
        path = self._path(project_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {"project_id": project_id,
                 "updated_at": datetime.now(timezone.utc).isoformat(),
                 "predictions": [p.model_dump() for p in predictions]},
                f, indent=2,
            )

    # ── Capture ───────────────────────────────────────────────────────
    def capture_from_reports(self, project_id: str, reports: Dict[str, Any],
                             iteration: int = 1) -> List[Prediction]:
        """Snapshot tracked handoff metrics from consensus-approved reports.

        `reports` is {agent_name: WarRoomReport}. Re-capturing the same
        project replaces unreconciled predictions but preserves any that
        already carry actuals.
        """
        existing = self._load(project_id)
        reconciled = [p for p in existing if p.actual is not None]
        reconciled_keys = {(p.agent, p.metric) for p in reconciled}

        captured: List[Prediction] = []
        for agent, specs in TRACKED_METRICS.items():
            report = reports.get(agent)
            if report is None:
                continue
            hp = getattr(report, "handoff_payload", None) or {}
            for spec in specs:
                if (agent, spec["metric"]) in reconciled_keys:
                    continue  # reality already recorded — don't overwrite
                raw = hp.get(spec["metric"])
                try:
                    value = float(raw)
                except (TypeError, ValueError):
                    continue
                if value == 0:
                    continue  # default-filled, not a real claim
                captured.append(Prediction(
                    prediction_id=f"{project_id}:{agent}:{spec['metric']}",
                    project_id=project_id,
                    agent=agent,
                    metric=spec["metric"],
                    predicted=value,
                    unit=spec["unit"],
                    direction=spec["direction"],
                    tolerance_pct=spec["tolerance_pct"],
                    iteration=iteration,
                ))

        self._save(project_id, reconciled + captured)
        logger.info(f"[Ledger] Captured {len(captured)} predictions for {project_id}")
        return captured

    # ── Reconciliation ────────────────────────────────────────────────
    def record_actual(self, project_id: str, metric: str, actual: float,
                      source: str = "manual") -> Optional[Prediction]:
        """Record reality for one metric. Returns the reconciled prediction
        (with error and tripwire state) or None if no such prediction."""
        predictions = self._load(project_id)
        target = next((p for p in predictions if p.metric == metric), None)
        if target is None:
            return None

        target.actual = float(actual)
        target.recorded_at = datetime.now(timezone.utc).isoformat()
        target.source = source
        if target.predicted:
            target.error_pct = round(
                (target.actual - target.predicted) / abs(target.predicted) * 100, 1)
            tol = target.tolerance_pct
            if target.direction == "over_is_bad":
                target.tripwire_fired = target.error_pct > tol
            else:
                target.tripwire_fired = target.error_pct < -tol

        self._save(project_id, predictions)
        if target.tripwire_fired:
            self._emit_tripwire_alert(target)
        return target

    def _emit_tripwire_alert(self, p: Prediction):
        """Persist a tripwire alert for the monitoring plane / dashboard."""
        alert = {
            "type": "PREDICTION_TRIPWIRE",
            "project_id": p.project_id,
            "agent": p.agent,
            "metric": p.metric,
            "predicted": p.predicted,
            "actual": p.actual,
            "error_pct": p.error_pct,
            "severity": "HIGH",
            "acknowledged": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": (
                f"Plan assumption violated: {p.agent} predicted {p.metric}="
                f"{p.predicted}{p.unit}, reality is {p.actual}{p.unit} "
                f"({p.error_pct:+.0f}%). Reconvene the War Room for "
                f"{p.project_id}."
            ),
        }
        try:
            existing = []
            if os.path.exists(self.alerts_path):
                with open(self.alerts_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            existing.append(alert)
            with open(self.alerts_path, "w", encoding="utf-8") as f:
                json.dump(existing[-100:], f, indent=2)
        except Exception as e:
            logger.error(f"[Ledger] Failed to persist tripwire alert: {e}")
        logger.warning(f"[Ledger] TRIPWIRE: {alert['message']}")

    # ── Queries ───────────────────────────────────────────────────────
    def list_predictions(self, project_id: str) -> List[Prediction]:
        return self._load(project_id)

    def fired_tripwires(self, project_id: str = None) -> List[dict]:
        if not os.path.exists(self.alerts_path):
            return []
        try:
            with open(self.alerts_path, "r", encoding="utf-8") as f:
                alerts = json.load(f)
        except Exception:
            return []
        if project_id:
            alerts = [a for a in alerts if a.get("project_id") == project_id]
        return alerts

    def _all_predictions(self) -> List[Prediction]:
        out: List[Prediction] = []
        if not os.path.isdir(self.base_dir):
            return out
        for fname in os.listdir(self.base_dir):
            if fname.endswith(".json") and fname != "tripwire_alerts.json":
                out.extend(self._load(fname[:-5]))
        return out

    # ── Calibration ───────────────────────────────────────────────────
    def agent_calibration(self, agent: str = None) -> Dict[str, Any]:
        """Per-(agent, metric) signed-error statistics across all
        reconciled predictions. Positive mean error = reality exceeded
        the prediction."""
        reconciled = [p for p in self._all_predictions() if p.error_pct is not None]
        if agent:
            reconciled = [p for p in reconciled if p.agent == agent.upper()]

        stats: Dict[str, Dict[str, Any]] = {}
        for p in reconciled:
            key = f"{p.agent}.{p.metric}"
            s = stats.setdefault(key, {"agent": p.agent, "metric": p.metric,
                                       "errors": [], "tripwires": 0})
            s["errors"].append(p.error_pct)
            if p.tripwire_fired:
                s["tripwires"] += 1

        for s in stats.values():
            errs = s.pop("errors")
            s["n"] = len(errs)
            s["mean_error_pct"] = round(sum(errs) / len(errs), 1)
            s["worst_error_pct"] = round(max(errs, key=abs), 1)
        return stats

    def calibration_prompt_block(self, agent: str) -> str:
        """Render the agent's track record as prompt context. Empty string
        when there is no reconciled history (no noise on cold start)."""
        stats = self.agent_calibration(agent)
        if not stats:
            return ""
        lines = [f"=== YOUR CALIBRATION RECORD (predictions vs. reality) ==="]
        for s in stats.values():
            if s["n"] < 1:
                continue
            bias = ("reality came in HIGHER than your estimates"
                    if s["mean_error_pct"] > 0
                    else "reality came in LOWER than your estimates")
            lines.append(
                f"- {s['metric']}: avg {s['mean_error_pct']:+.0f}% vs actuals "
                f"(n={s['n']}) — {bias}. Correct for this bias in today's numbers."
            )
        if len(lines) == 1:
            return ""
        return "\n".join(lines)

    # ── Reference class (base rates for the Critic) ──────────────────
    def reference_class(self, metric: str) -> List[float]:
        """All predicted values ever captured for a metric, across projects."""
        return sorted(p.predicted for p in self._all_predictions() if p.metric == metric)

    def base_rate_block(self, current_values: Dict[str, float],
                        min_history: int = 3) -> str:
        """Render where the current plan's claims sit against every plan
        the War Room has ever approved. Used as Critic ammunition."""
        lines = []
        for metric, value in current_values.items():
            try:
                value = float(value)
            except (TypeError, ValueError):
                continue
            if value == 0:
                continue
            history = self.reference_class(metric)
            if len(history) < min_history:
                continue
            below = sum(1 for h in history if h <= value)
            pct = round(below / len(history) * 100)
            lines.append(
                f"- {metric}={value:g} sits at P{pct} of {len(history)} past "
                f"approved plans (median {history[len(history)//2]:g})."
            )
        if not lines:
            return ""
        return (
            "=== BASE RATES (this plan vs. every plan ever approved) ===\n"
            + "\n".join(lines)
            + "\nClaims in the top decile of historical optimism require "
              "specific evidence — challenge them."
        )


# ── Module-level singleton ────────────────────────────────────────────
_ledger: Optional[PredictionLedger] = None


def get_prediction_ledger() -> PredictionLedger:
    global _ledger
    if _ledger is None:
        _ledger = PredictionLedger()
    return _ledger
