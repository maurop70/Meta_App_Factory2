"""
ClaudeAY panel package (Phase 1).

DETECTION ONLY at this phase: fail-closed seat-caller + honest lineage reporting.
Nothing in this package imports the executor path (no send_mandate, no
executor_gate.mint, no loop dispatch). It cannot mint a token, dispatch a mandate,
or change code. Later phases (seats → chair → scope → gate) build on top.
"""
