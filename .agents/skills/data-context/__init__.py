"""data-context skill — reusable source ingestion + derivation engine (stages B–F)."""
try:
    from .data_context import (DataContext, Table, reconcile_matrix, match_category)
except ImportError:
    from data_context import (DataContext, Table, reconcile_matrix, match_category)

__all__ = ["DataContext", "Table", "reconcile_matrix", "match_category"]
