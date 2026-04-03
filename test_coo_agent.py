import pytest
from coo_agent import COOManager, OpBudgetExceeded

def test_coo_tracking_and_budgeting():
    coo = COOManager()
    pid = "test_project"
    
    # Send a small query
    ledge = coo.record_usage(pid, "CMO", "prompt text", "response text here")
    assert ledge.tokens_in > 0
    assert ledge.tokens_out > 0
    assert ledge.total_tokens == ledge.tokens_in + ledge.tokens_out
    assert ledge.status == "active"
    
    # Exhaust the budget manually
    coo.get_ledger(pid).tokens_out = 99990
    
    # This should throw the error
    with pytest.raises(OpBudgetExceeded):
        coo.record_usage(pid, "CTO", "large prompt " * 100, "large response " * 100)
    
    assert coo.get_ledger(pid).status == "halted"

def test_ledger_reset():
    coo = COOManager()
    pid = "test_project2"
    coo.record_usage(pid, "CMO", "hello", "world")
    assert coo.get_ledger(pid).total_tokens > 0
    
    coo.reset_ledger(pid)
    assert coo.get_ledger(pid).total_tokens == 0
    assert coo.get_ledger(pid).status == "active"
