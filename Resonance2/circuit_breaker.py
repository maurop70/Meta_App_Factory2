"""
Antigravity Circuit Breaker — Prevents cascade failures in N8N webhook calls.
Usage:
    from circuit_breaker import CircuitBreaker
    cb = CircuitBreaker("genesis-v3")  
    
    if cb.can_call():
        try:
            response = requests.post(url, json=payload, timeout=30)
            cb.record_success()
        except Exception as e:
            cb.record_failure()
    else:
        print("Circuit OPEN — skipping call")
"""
import os, sys, json, time
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.join(os.path.expanduser("~"), ".antigravity", "circuit_breakers")


class CircuitBreaker:
    """
    Circuit Breaker pattern for N8N webhook calls.
    
    States:
        CLOSED  — Normal operation, calls go through
        OPEN    — Failures exceeded threshold, calls blocked for cooldown period
        HALF_OPEN — Cooldown expired, one test call allowed
    
    Config:
        failure_threshold: consecutive failures before opening (default: 5)
        cooldown_seconds:  how long OPEN state lasts (default: 300 = 5 min)
        success_threshold: successes in HALF_OPEN to close (default: 2)
    """

    def __init__(self, name, failure_threshold=5, cooldown_seconds=300, success_threshold=2):
        self.name = name
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.success_threshold = success_threshold
        self.state_file = os.path.join(STATE_DIR, f"{name}.json")
        os.makedirs(STATE_DIR, exist_ok=True)
        self._state = self._load_state()

    def _load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "state": "CLOSED",
            "consecutive_failures": 0,
            "consecutive_successes": 0,
            "total_failures": 0,
            "total_successes": 0,
            "last_failure_time": None,
            "opened_at": None,
        }

    def _save_state(self):
        try:
            with open(self.state_file, "w") as f:
                json.dump(self._state, f, indent=2)
        except Exception:
            pass

    @property
    def state(self):
        """Get current circuit state, considering cooldown expiration."""
        if self._state["state"] == "OPEN" and self._state.get("opened_at"):
            elapsed = time.time() - self._state["opened_at"]
            if elapsed >= self.cooldown_seconds:
                self._state["state"] = "HALF_OPEN"
                self._state["consecutive_successes"] = 0
                self._save_state()
        return self._state["state"]

    def can_call(self):
        """Check if a call is allowed through the circuit breaker."""
        current = self.state
        if current == "CLOSED":
            return True
        elif current == "HALF_OPEN":
            return True  # Allow one test call
        else:  # OPEN
            remaining = self.cooldown_seconds - (time.time() - self._state.get("opened_at", 0))
            return False

    def record_success(self):
        """Record a successful call."""
        self._state["total_successes"] += 1
        self._state["consecutive_failures"] = 0

        if self._state["state"] == "HALF_OPEN":
            self._state["consecutive_successes"] += 1
            if self._state["consecutive_successes"] >= self.success_threshold:
                self._state["state"] = "CLOSED"
                self._state["opened_at"] = None
                print(f"  🟢 Circuit [{self.name}]: CLOSED (recovered)")
        else:
            self._state["state"] = "CLOSED"

        self._save_state()

    def record_failure(self):
        """Record a failed call."""
        self._state["total_failures"] += 1
        self._state["consecutive_failures"] += 1
        self._state["consecutive_successes"] = 0
        self._state["last_failure_time"] = datetime.now().isoformat()

        if self._state["consecutive_failures"] >= self.failure_threshold:
            if self._state["state"] != "OPEN":
                self._state["state"] = "OPEN"
                self._state["opened_at"] = time.time()
                print(f"  🔴 Circuit [{self.name}]: OPEN — {self._state['consecutive_failures']} consecutive failures. "
                      f"Cooling down for {self.cooldown_seconds}s.")
                # Log to error aggregator if available
                try:
                    from error_aggregator import ErrorAggregator
                    ErrorAggregator("CircuitBreaker").log_warning(
                        f"Circuit OPENED for {self.name}",
                        context={"failures": self._state["consecutive_failures"]}
                    )
                except ImportError:
                    pass

        self._save_state()

    def reset(self):
        """Manually reset the circuit breaker."""
        self._state = {
            "state": "CLOSED",
            "consecutive_failures": 0,
            "consecutive_successes": 0,
            "total_failures": self._state.get("total_failures", 0),
            "total_successes": self._state.get("total_successes", 0),
            "last_failure_time": None,
            "opened_at": None,
        }
        self._save_state()
        print(f"  🔄 Circuit [{self.name}]: RESET to CLOSED")

    def get_status(self):
        """Get a status dict for telemetry/dashboards."""
        current = self.state
        result = {
            "name": self.name,
            "state": current,
            "consecutive_failures": self._state["consecutive_failures"],
            "total_failures": self._state["total_failures"],
            "total_successes": self._state["total_successes"],
        }
        if current == "OPEN" and self._state.get("opened_at"):
            remaining = max(0, self.cooldown_seconds - (time.time() - self._state["opened_at"]))
            result["cooldown_remaining_s"] = round(remaining)
        return result


def protected_call(name, call_fn, *args, **kwargs):
    """
    Convenience wrapper — wraps any callable with circuit breaker protection.
    Usage:
        result = protected_call("genesis", requests.post, url, json=payload, timeout=30)
    """
    cb = CircuitBreaker(name)
    if not cb.can_call():
        remaining = cb.cooldown_seconds - (time.time() - cb._state.get("opened_at", 0))
        raise ConnectionError(
            f"Circuit breaker [{name}] is OPEN. "
            f"Retry in {max(0, int(remaining))}s."
        )
    try:
        result = call_fn(*args, **kwargs)
        cb.record_success()
        return result
    except Exception as e:
        cb.record_failure()
        raise


# ── CLI ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n{'='*55}")
    print(f"  CIRCUIT BREAKER STATUS")
    print(f"{'='*55}\n")

    if not os.path.exists(STATE_DIR):
        print("  No circuit breakers registered yet.")
    else:
        for fname in os.listdir(STATE_DIR):
            if fname.endswith(".json"):
                name = fname[:-5]
                cb = CircuitBreaker(name)
                s = cb.get_status()
                icons = {"CLOSED": "🟢", "OPEN": "🔴", "HALF_OPEN": "🟡"}
                icon = icons.get(s["state"], "❓")
                line = f"  {icon} {s['name']}: {s['state']} (failures: {s['total_failures']}, successes: {s['total_successes']})"
                if s.get("cooldown_remaining_s"):
                    line += f" — cooldown: {s['cooldown_remaining_s']}s"
                print(line)

    print(f"\n{'='*55}\n")
