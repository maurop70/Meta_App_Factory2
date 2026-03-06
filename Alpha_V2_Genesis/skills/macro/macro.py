class MacroAgent:
    def __init__(self):
        pass

    def analyze_calendar(self, n8n_events=None):
        """
        Returns macro risk analysis. 
        If n8n_events is provided (even if empty list), uses that real-time data.
        Otherwise, defaults to a safe/empty state.
        """
        if n8n_events is not None:
            # We have real data (or a confirmed empty list)
            risk = "LOW"
            if isinstance(n8n_events, list):
                for e in n8n_events:
                    if e.get('impact') == 'HIGH' and e.get('days_until', 99) <= 3:
                        risk = "HIGH"
                    elif e.get('impact') == 'MED' and e.get('days_until', 99) <= 1 and risk != "HIGH":
                         risk = "MEDIUM"
                
                high_impact = [e.get('event') for e in n8n_events if e.get('impact') == 'HIGH']
                description = f"Analysis based on {len(n8n_events)} upcoming events."
                if high_impact:
                    description += f" HIGH IMPACT: {', '.join(high_impact)}"
            else:
                description = "Macro data format invalid."
            
            return {
                "risk_level": risk,
                "events": n8n_events,
                "details": description
            }

        # Fallback: No Data (Don't show wrong data)
        return {
            "risk_level": "LOW",
            "events": [],
            "details": "No specific high-impact events detected in current scan."
        }
