"""
strategic_sentiment.py — CMO Sentiment Port (V3 Live)
══════════════════════════════════════════════════════
Thin compatibility wrapper around cmo_agent.py.
Preserved for backward compatibility with any existing callers.
All live intelligence now flows through cmo_agent.run_cmo_analysis().
"""
from cmo_agent import run_cmo_analysis


class StrategicSentimentAnalyzer:
    def analyze_market(self, project_id: str) -> dict:
        """Backward-compatible interface. Delegates to live CMO agent."""
        return run_cmo_analysis(project_id)


_analyzer = StrategicSentimentAnalyzer()


def get_strategic_sentiment() -> StrategicSentimentAnalyzer:
    return _analyzer
