"""
data_validation_engine.py -- Alpha V2 Genesis DataValidationEngine
====================================================================
Meta App Factory | Alpha_V2_Genesis | Antigravity-AI

Scans all inbound analytical data before fragility/strategy decisions.
If values are null or outside logical bounds, outputs a 'Signal Warning'
instead of a decision recommendation. PII masking on all output logs.
"""

# ── V3.0 Resilience Integration ──────────────────────────
import os as _os, sys as _sys
_FACTORY_DIR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_sys.path.insert(0, _FACTORY_DIR)
try:
    from factory import safe_post
    from local_state_manager import StateManager as _StateManager
    _v3_sm = _StateManager()
    _V3_AVAILABLE = True
except ImportError:
    _V3_AVAILABLE = False
# ── End V3 Integration ──────────────────────────────────

from auto_heal import healed_post, auto_heal, diagnose

def _v3_preflight():
    """V3: Ping Resonance_Watchdog_V3 before execution."""
    if not _V3_AVAILABLE:
        return True
    try:
        import json as _j
        _cfg_path = _os.path.join(_FACTORY_DIR, "resilience_config.json")
        if not _os.path.exists(_cfg_path):
            return True
        with open(_cfg_path) as _f:
            _cfg = _j.load(_f)
        _url = _cfg.get("cloud_health", {}).get("watchdog_url", "")
        if not _url:
            return True
        import requests as _rq
        _r = _rq.get(_url, timeout=5)
        return _r.status_code == 200
    except Exception:
        return False


import os
import sys
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("alpha.validation")

SCRIPT_DIR = Path(__file__).resolve().parent
FACTORY_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(FACTORY_DIR))
sys.path.insert(0, str(FACTORY_DIR / "Sentinel_Bridge"))

MASTER_INDEX_PATH = FACTORY_DIR / "MASTER_INDEX.md"

# Lazy imports
_pii = None


def _get_pii():
    global _pii
    if _pii is None:
        try:
            from pii_masker import PIIMasker
            _pii = PIIMasker()
        except ImportError:
            pass
    return _pii


# ── Validation Rules ─────────────────────────────────────

VALIDATION_RULES = {
    # Fragility Engine fields
    "vix": {"type": "float", "min": 0, "max": 150, "nullable": True,
            "label": "VIX Index"},
    "vix3m": {"type": "float", "min": 0, "max": 150, "nullable": True,
              "label": "VIX 3-Month"},
    "vix_ratio": {"type": "float", "min": 0.1, "max": 5.0, "nullable": True,
                  "label": "VIX/VIX3M Ratio"},
    "skew": {"type": "float", "min": 80, "max": 200, "nullable": True,
             "label": "CBOE Skew Index"},
    "spy_tlt_corr_20d": {"type": "float", "min": -1, "max": 1, "nullable": True,
                         "label": "SPY/TLT 20d Correlation"},
    "spy_tlt_corr_60d": {"type": "float", "min": -1, "max": 1, "nullable": True,
                         "label": "SPY/TLT 60d Correlation"},
    "hyg_iei_ratio": {"type": "float", "min": 0.01, "max": 10, "nullable": True,
                      "label": "HYG/IEI Credit Ratio"},
    "hyg_iei_zscore": {"type": "float", "min": -10, "max": 10, "nullable": True,
                       "label": "Credit Z-Score"},
    "volume_zscore": {"type": "float", "min": -10, "max": 10, "nullable": True,
                      "label": "Volume Z-Score"},
    "fragility_index": {"type": "int", "min": 0, "max": 100, "nullable": False,
                        "label": "Fragility Index"},
    "confidence_score": {"type": "int", "min": 0, "max": 100, "nullable": False,
                         "label": "Data Confidence Score"},
}


class SignalWarning:
    """Represents a data quality warning that blocks decision output."""

    def __init__(self, field: str, issue: str, value: Any,
                 severity: str = "warning"):
        self.field = field
        self.issue = issue
        self.value = value
        self.severity = severity  # "warning", "critical"
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "field": self.field,
            "issue": self.issue,
            "value": str(self.value)[:100],
            "severity": self.severity,
            "timestamp": self.timestamp,
        }

    def __repr__(self):
        return f"SignalWarning({self.field}: {self.issue})"


class DataValidationEngine:
    """
    Validates inbound analytical data before any decision logic runs.
    Blocks bad data with SignalWarnings instead of false recommendations.
    """

    def __init__(self):
        self._warnings: list = []
        self._pii = _get_pii()

    # ── Core: Validate Data ──────────────────────────────

    def validate(self, data: dict, rules: dict = None) -> dict:
        """
        Validate a data payload against rules.
        Returns validation result with pass/fail and warnings.
        """
        rules = rules or VALIDATION_RULES
        self._warnings = []
        fields_checked = 0
        fields_passed = 0

        for field_name, rule in rules.items():
            value = self._deep_get(data, field_name)
            fields_checked += 1

            # Null check
            if value is None:
                if not rule.get("nullable", True):
                    self._warnings.append(SignalWarning(
                        field=field_name,
                        issue=f"{rule.get('label', field_name)} is NULL "
                              f"(required for decision output)",
                        value=None,
                        severity="critical",
                    ))
                    continue
                else:
                    fields_passed += 1
                    continue

            # Type check
            expected_type = rule.get("type", "float")
            try:
                if expected_type == "float":
                    value = float(value)
                elif expected_type == "int":
                    value = int(value)
            except (ValueError, TypeError):
                self._warnings.append(SignalWarning(
                    field=field_name,
                    issue=f"{rule.get('label', field_name)} has invalid type "
                          f"(expected {expected_type}, got {type(value).__name__})",
                    value=value,
                    severity="critical",
                ))
                continue

            # Bounds check
            min_val = rule.get("min")
            max_val = rule.get("max")
            if min_val is not None and value < min_val:
                self._warnings.append(SignalWarning(
                    field=field_name,
                    issue=f"{rule.get('label', field_name)} = {value} is below "
                          f"logical minimum ({min_val})",
                    value=value,
                    severity="warning",
                ))
                continue

            if max_val is not None and value > max_val:
                self._warnings.append(SignalWarning(
                    field=field_name,
                    issue=f"{rule.get('label', field_name)} = {value} exceeds "
                          f"logical maximum ({max_val})",
                    value=value,
                    severity="warning",
                ))
                continue

            fields_passed += 1

        # Determine overall result
        critical_count = sum(
            1 for w in self._warnings if w.severity == "critical"
        )
        warning_count = len(self._warnings) - critical_count

        if critical_count > 0:
            status = "SIGNAL_WARNING"
            recommendation = (
                "DATA QUALITY INSUFFICIENT: Cannot produce reliable "
                "decision recommendation. Resolve critical data issues "
                "before re-running analysis."
            )
        elif warning_count > 2:
            status = "SIGNAL_WARNING"
            recommendation = (
                "MULTIPLE DATA WARNINGS: Decision output may be unreliable. "
                "Review flagged fields before acting on recommendations."
            )
        elif warning_count > 0:
            status = "CAUTION"
            recommendation = (
                "Minor data quality issues detected. Decision output is "
                "available but should be reviewed with caution."
            )
        else:
            status = "VALID"
            recommendation = "All data validated. Decision output is reliable."

        result = {
            "status": status,
            "recommendation": recommendation,
            "fields_checked": fields_checked,
            "fields_passed": fields_passed,
            "critical_warnings": critical_count,
            "warnings": warning_count,
            "details": [w.to_dict() for w in self._warnings],
            "validated_at": datetime.now(timezone.utc).isoformat(),
        }

        # PII-mask the log
        if self._pii:
            result["recommendation"] = self._pii.mask(result["recommendation"])

        return result

    def _deep_get(self, data: dict, key: str) -> Any:
        """Get a value from nested data by key name."""
        if key in data:
            return data[key]
        # Search one level deep in sub-dicts
        for v in data.values():
            if isinstance(v, dict) and key in v:
                return v[key]
        return None

    # ── Wrapper: Validate Before Decision ────────────────

    def validate_before_decision(self, fragility_payload: dict) -> dict:
        """
        Wrapper for fragility_engine output.
        If validation fails, replaces the decision with a Signal Warning.
        """
        # Extract key fields from nested payload
        flat = {}
        for key in VALIDATION_RULES:
            val = self._deep_get(fragility_payload, key)
            if val is not None:
                flat[key] = val

        validation = self.validate(flat)

        if validation["status"] == "SIGNAL_WARNING":
            # Override the decision
            logger.warning(
                "Signal Warning: %d critical, %d warnings",
                validation["critical_warnings"],
                validation["warnings"],
            )
            return {
                "signal_warning": True,
                "validation": validation,
                "original_fragility": fragility_payload.get(
                    "fragility_index", None
                ),
                "decision_blocked": True,
                "message": validation["recommendation"],
            }

        return {
            "signal_warning": False,
            "validation": validation,
            "decision_blocked": False,
        }

    def get_warnings(self) -> list:
        """Return current warnings."""
        return [w.to_dict() for w in self._warnings]


# ── Entry Point ──────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(message)s")

    parser = argparse.ArgumentParser(
        description="Alpha V2 DataValidationEngine"
    )
    parser.add_argument("--test", action="store_true",
                        help="Run validation with test data")
    args = parser.parse_args()

    engine = DataValidationEngine()

    if args.test:
        print("DataValidationEngine -- Self-Test")
        print("-" * 50)

        # Test 1: Valid data
        good_data = {
            "vix": 18.5, "vix3m": 20.1, "vix_ratio": 0.92,
            "skew": 132.5, "spy_tlt_corr_20d": -0.25,
            "hyg_iei_ratio": 0.72, "hyg_iei_zscore": 0.3,
            "fragility_index": 35, "confidence_score": 78,
        }
        r1 = engine.validate(good_data)
        print(f"1. Valid data:   status={r1['status']}, "
              f"passed={r1['fields_passed']}/{r1['fields_checked']}")

        # Test 2: Data with nulls (critical fields)
        bad_data = {
            "vix": None, "vix3m": None, "vix_ratio": None,
            "fragility_index": None, "confidence_score": None,
        }
        r2 = engine.validate(bad_data)
        print(f"2. Null criticals: status={r2['status']}, "
              f"critical={r2['critical_warnings']}")
        for w in r2["details"]:
            print(f"   -> {w['field']}: {w['issue']}")

        # Test 3: Out-of-bounds
        oob_data = {
            "vix": 200, "spy_tlt_corr_20d": 5.0,
            "fragility_index": 150, "confidence_score": -10,
        }
        r3 = engine.validate(oob_data)
        print(f"\n3. Out-of-bounds: status={r3['status']}, "
              f"warnings={r3['warnings']}")
        for w in r3["details"]:
            print(f"   -> {w['field']}: {w['issue']}")

        # Test 4: Wrapper test
        mock_fragility = {
            "fragility_index": 45,
            "confidence_score": 60,
            "volatility": {"vix": None, "vix3m": None, "score": 50},
            "correlations": {"spy_tlt_corr_20d": None},
            "credit": {"hyg_iei_ratio": None},
        }
        r4 = engine.validate_before_decision(mock_fragility)
        print(f"\n4. Wrapper test: signal_warning={r4['signal_warning']}, "
              f"blocked={r4['decision_blocked']}")

        print("\nAll tests complete!")
    else:
        print("Use --test to run validation self-test.")
# V3 AUTO-HEAL ACTIVE
