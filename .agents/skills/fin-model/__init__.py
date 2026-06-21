"""fin-model skill — live, formula-driven Excel financial models (MAF native stack)."""
try:
    from .fin_model import FinModel, build_and_verify, shadow_model, scenario_ebitda
    from .verify import run_full_check
except ImportError:  # when imported as a flat module via sys.path insert
    from fin_model import FinModel, build_and_verify, shadow_model, scenario_ebitda
    from verify import run_full_check

__all__ = ["FinModel", "build_and_verify", "run_full_check", "shadow_model", "scenario_ebitda"]
