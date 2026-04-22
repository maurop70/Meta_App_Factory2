"""
mlops_watchdog.py — Agent Drift and Performance Monitoring
══════════════════════════════════════════════════════════
CIO Discovery #3: MLOps for Production-Grade Agents.
Tracks agent response times, success rates, and score drift
to ensure operational stability at scale.
"""

import os
import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, List

logger = logging.getLogger("MLOpsWatchdog")

class MLOpsWatchdog:
    def __init__(self, baseline_path: str = "agent_baselines.json"):
        self.baseline_path = baseline_path
        self.metrics = self._load_baselines()
        self.current_session = {}

    def _load_baselines(self) -> Dict[str, Any]:
        if os.path.exists(self.baseline_path):
            try:
                with open(self.baseline_path) as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_metrics(self):
        with open(self.baseline_path, "w") as f:
            json.dump(self.metrics, f, indent=4)

    def log_performance(self, agent_name: str, duration: float, success: bool):
        """Logs latency and success for a single agent call."""
        if agent_name not in self.metrics:
            self.metrics[agent_name] = {"latency_avg": 0, "calls": 0, "errors": 0, "scores": []}
        
        m = self.metrics[agent_name]
        m["calls"] += 1
        if not success:
            m["errors"] += 1
        
        # Simple moving average for latency
        m["latency_avg"] = (m["latency_avg"] * (m["calls"] - 1) + duration) / m["calls"]
        logger.info(f"MLOps: {agent_name} latency recorded: {duration:.2f}s")

    def log_score_drift(self, agent_name: str, score: float):
        """Detects if an agent's score output (e.g. CFO score) is drifting."""
        if agent_name not in self.metrics:
            self.metrics[agent_name] = {"latency_avg": 0, "calls": 0, "errors": 0, "scores": []}
        
        scores = self.metrics[agent_name].get("scores", [])
        scores.append({"score": score, "timestamp": datetime.now().isoformat()})
        
        # Keep last 10 scores
        if len(scores) > 10:
            scores.pop(0)
        
        self.metrics[agent_name]["scores"] = scores

        # Simple drift detection: if current score is >20% lower than avg of last 5
        if len(scores) > 5:
            avg_last_5 = sum(s["score"] for s in scores[-6:-1]) / 5
            if score < avg_last_5 * 0.8:
                self._alert_drift(agent_name, score, avg_last_5)

    def _alert_drift(self, agent_name: str, current: float, baseline: float):
        msg = f"⚠️ [MLOps ALERT] Drift detected in {agent_name}! Current: {current} | Baseline: {baseline:.2f}"
        logger.warning(msg)
        # Standard Antigravity auto_heal hook
        try:
            from auto_heal import _log_heal_event
            _log_heal_event("MLOpsWatchdog", f"{agent_name} Drift", {"current": current, "baseline": baseline}, "WATCHDOG_ALERT")
        except:
            pass

    def get_summary(self) -> Dict[str, Any]:
        return self.metrics
