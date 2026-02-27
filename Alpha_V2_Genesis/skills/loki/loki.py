from skills.risk.risk import RiskAgent
from skills.macro.macro import MacroAgent
from skills.watchdog.watchdog_v2 import WatchdogAgent
from skills.sentiment.sentiment import SentimentAgent
from skills.n8n_pusher import push_decision
import logging
import json
import os
import re
import requests
import yfinance as yf
from datetime import datetime, timedelta

# V2.0 Vault integration — 3-tier fallback (vault → env → .env)
try:
    # Navigate from skills/loki/ up to Alpha_V2_Genesis root
    import sys as _sys
    _alpha_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if _alpha_root not in _sys.path:
        _sys.path.insert(0, _alpha_root)
    from vault_client import get_secret
except ImportError:
    # Fallback if vault_client not available
    def get_secret(key, default="", **kw):
        return os.getenv(key, default)

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("LokiSkill")

from utils.system_alerts import play_alert_sound, show_popup
from skills.opinion.opinion import OpinionAgent

class Loki:
    def __init__(self, portfolio_path=None):
        logger.info("Loki Initializing...")
        self.risk = RiskAgent()
        self.macro = MacroAgent()
        self.dop = OpinionAgent() # The new Brain for Opinions
        self.watchdog = WatchdogAgent(portfolio_path)
        self.sentiment = SentimentAgent()
    # Cache for Option Chains
        self.chain_cache = {} 
        self.cache_expiry = {}

    def get_dynamic_expiration(self, ticker_symbol="^SPX", target_days=7):
        """
        Fetches dynamic expiration dates from Yahoo Finance.
        Returns the expiration date closest to the target_days.
        """
        try:
            ticker = yf.Ticker(ticker_symbol)
            expirations = ticker.options
            
            today = datetime.now().date()
            best_date = None
            min_diff = float('inf')
            
            for exp_str in expirations:
                exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
                days_diff = (exp_date - today).days
                
                if days_diff < 0: continue
                
                diff_from_target = abs(days_diff - target_days)
                if diff_from_target < min_diff:
                    min_diff = diff_from_target
                    best_date = exp_str
            
            if not best_date and expirations:
                best_date = expirations[0]

            logger.info(f"Dynamic Date Selected: {best_date} (Target: {target_days} DTE)")
            return best_date

        except Exception as e:
            logger.error(f"Failed to fetch dynamic expiration: {e}")
            fallback = (datetime.now() + timedelta(days=target_days)).strftime("%Y-%m-%d")
            return fallback

    def get_cached_chain(self, ticker_symbol, expiration):
        """
        Fetches option chain with 60-second caching to prevent freezing.
        """
        now = datetime.now().timestamp()
        key = f"{ticker_symbol}_{expiration}"
        
        if key in self.chain_cache:
            if now < self.cache_expiry.get(key, 0):
                logger.info(f"Using Cached Chain for {key}")
                return self.chain_cache[key]
        
        # Fetch New
        logger.info(f"Fetching Live Chain for {key}...")
        try:
            ticker = yf.Ticker(ticker_symbol)
            chain = ticker.option_chain(expiration)
            self.chain_cache[key] = chain
            self.cache_expiry[key] = now + 60 # Cache for 60 seconds
            return chain
        except Exception as e:
            logger.error(f"Failed to fetch chain {key}: {e}")
            return None

    def generate_analyst_memo(self, decision):
        """
        Generates the market_memo.md using the required template.
        """
        try:
            from datetime import datetime
            
            # Field Mapping Fix: Decision contains 'loki_proposal' which has strategy details
            proposal = decision.get('loki_proposal', {})
            strategy_type = proposal.get('strategy', 'Unknown')
            vix_level = decision.get('market_snapshot', {}).get('vix', 20.0)
            delta_selection = proposal.get('delta', 0.15)
            
            # Extract Macro Events for the Report
            macro_events = decision.get('expert_opinions', {}).get('macro', {}).get('events', [])
            event_summary = ""
            if macro_events:
                event_summary = "\n### 🛡️ 7-Day Macro Outlook\n"
                for e in macro_events:
                    color = "🔴" if e.get('impact') == 'HIGH' else "🟡"
                    event_summary += f"* {color} **{e.get('event')}** (In {e.get('days_until')}d)\n"
            else:
                 event_summary = "\n### 🛡️ 7-Day Macro Outlook\n* ✅ No high-impact binary events detected in the current window."

            report = f"""# ALPHA ARCHITECT: SYSTEM RATIONALE
**Timestamp:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Recommended Strategy:** {strategy_type}

### Market Regime Analysis
* **VIX Level:** {vix_level}
* **Rationale:** {"Quiet market detected; favoring 7 DTE for rapid theta decay." if vix_level < 15 else "Volatility present; favoring 45 DTE for higher premium and safety margin."}
{event_summary}

### Execution Parameters
* **Delta Range:** {delta_selection}
* **Management Rule:** {"CLOSE AT 21 DTE" if "45 DTE" in strategy_type else "CLOSE AT EXPIRATION/STOP"}
* **Profit Target:** 50% of Max Credit.

### Risk Warning
{"CAUTION: 0.20 Delta selected. Ensure strict 21 DTE exit to avoid Gamma exposure." if delta_selection >= 0.20 else "Standard risk profile active."}
"""
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            memo_path = os.path.join(project_root, "market_memo.md")
            with open(memo_path, "w", encoding="utf-8") as f:
                f.write(report)
                
            logger.info("System Rationale Memo Updated with Macro Outlook.")
            
        except Exception as e:
            logger.error(f"Failed to write memo: {e}")

        
    def get_market_snapshot(self):
        try:
            # Use ^GSPC for more accurate real-time price on yfinance
            gspc_ticker = yf.Ticker("^GSPC")
            vix_ticker = yf.Ticker("^VIX")
            
            # Fetch history for more reliable price
            spx_hist = gspc_ticker.history(period="1d")
            vix_hist = vix_ticker.history(period="1d")
            
            current_spx = None
            current_vix = None

            if not spx_hist.empty:
                current_spx = spx_hist['Close'].iloc[-1]
            if not vix_hist.empty:
                current_vix = vix_hist['Close'].iloc[-1]
            
            # Fallback to info if history is somehow empty (rare but possible)
            if current_spx is None:
                current_spx = gspc_ticker.info.get('regularMarketPrice')
            if current_vix is None:
                current_vix = vix_ticker.info.get('regularMarketPrice')

            if current_spx is not None and current_vix is not None:
                # Calculate Trend (5d) using ^GSPC
                hist_5d = gspc_ticker.history(period="5d")
                trend = 0.0
                if not hist_5d.empty:
                    start = hist_5d['Close'].iloc[0]
                    end = current_spx
                    trend = ((end - start) / start) * 100
                
                # Calculate IV Rank (1 Year)
                vix_hist_1y = vix_ticker.history(period="1y")
                vix_low = vix_hist_1y['Low'].min() if not vix_hist_1y.empty else 10.0
                vix_high = vix_hist_1y['High'].max() if not vix_hist_1y.empty else 30.0
                iv_rank = 0
                if vix_high > vix_low:
                     iv_rank = ((current_vix - vix_low) / (vix_high - vix_low)) * 100
                     
                return {
                    "timestamp": datetime.now().timestamp(),
                    "spx": round(current_spx, 2),
                    "vix": round(current_vix, 2),
                    "iv_rank": round(iv_rank, 1),
                    "trend_5d_pct": round(trend, 2),
                    "news_count": 10 # Placeholder
                }
        except Exception as e:
            logger.error(f"Data Fetch Failed: {e}")
            
        # No hardcoded fallback - data must be live
        raise Exception("Market data fetch failed (SPX/VIX unavailable). Verify API/Internet connection.")

    def fetch_external_commentary(self):
        """
        Polls the cloud N8N workflow (Genesis v3 + SPX Polling) for AI-generated market research.
        Uses the inherited Meta_App_Factory bridge for connectivity.
        """
        try:
            # Import Heritage Bridge
            from utils.n8n_bridge import N8NBridge
            
            # BUDGET GUARD: Limit N8N executions to Mon-Tue, 9am-4pm
            import datetime
            now = datetime.datetime.now()
            is_window = (now.weekday() < 2) and (9 <= now.hour < 16)
            
            if not is_window:
                logger.info("Outside N8N Window (Mon-Tue, 9am-4pm). Returning cached intelligence.")
                return {
                    "forecast": "NEUTRAL",
                    "commentary": "N8N Cloud Brain is in Standby Mode (Outside Mon-Tue 9am-4pm window). Using local macro sensors.",
                    "risk_mode": "HOLD_RISK",
                    "n8n_live": False,
                    "events": []
                }

            # Step 1: Strategic Forecast (N8N Genesis Brain)
            # PRIMARY: Genesis v3 (structured JSON, self-healing, dynamic dates)
            # FALLBACK: Research v2 Robust (proven, raw text parsing)
            
            # 1. Gather Context
            snapshot = self.get_market_snapshot()
            logger.info(f"Polling N8N for Commentary (Context: SPX={snapshot['spx']})...")
            
            genesis_response = None
            
            # 2a. Try Genesis v3 (Primary)
            try:
                logger.info("Trying Genesis v3 (Primary)...")
                v3_bridge = N8NBridge(webhook_url="https://humanresource.app.n8n.cloud/webhook/alpha-research-v3")
                genesis_response = v3_bridge.execute_workflow(payload=snapshot)
                
                # Genesis v3 returns structured JSON directly (no 'text' wrapping needed)
                # But handle edge case where it still wraps in 'text'
                if genesis_response and isinstance(genesis_response, dict) and 'text' in genesis_response and 'forecast' not in genesis_response:
                    try:
                        raw_text = genesis_response['text']
                        json_match = re.search(r'\{.*\}', raw_text.replace('\n', ' '), re.DOTALL)
                        if json_match:
                            parsed = json.loads(json_match.group(0))
                            genesis_response.update(parsed)
                    except Exception as e:
                        logger.warning(f"Genesis v3 text parse failed: {e}")
                
                # Validate response has required fields
                if genesis_response and isinstance(genesis_response, dict) and 'forecast' in genesis_response:
                    genesis_response['n8n_live'] = True
                    genesis_response['n8n_source'] = 'Genesis v3'
                    logger.info("Genesis v3 SUCCESS — using structured intelligence.")
                else:
                    logger.warning("Genesis v3 returned incomplete data. Falling back to Research v2...")
                    genesis_response = None
                    
            except Exception as e:
                logger.warning(f"Genesis v3 failed: {e}. Falling back to Research v2...")
                genesis_response = None
            
            # 2b. Fallback to Research v2 Robust
            if not genesis_response or not isinstance(genesis_response, dict) or 'forecast' not in genesis_response:
                try:
                    logger.info("Trying Research v2 Robust (Fallback)...")
                    v2_bridge = N8NBridge(webhook_url="https://humanresource.app.n8n.cloud/webhook/alpha-research-v2")
                    genesis_response = v2_bridge.execute_workflow(payload=snapshot)
                    
                    # Research v2 returns raw text — parse it
                    if genesis_response and isinstance(genesis_response, dict) and 'text' in genesis_response:
                        try:
                            raw_text = genesis_response['text']
                            json_match = re.search(r'\{.*\}', raw_text.replace('\n', ' '), re.DOTALL)
                            if json_match:
                                parsed = json.loads(json_match.group(0))
                                genesis_response.update(parsed)
                        except Exception as e:
                            logger.warning(f"Research v2 text parse failed: {e}")
                    
                    if genesis_response and isinstance(genesis_response, dict):
                        genesis_response['n8n_live'] = True
                        genesis_response['n8n_source'] = 'Research v2 (Fallback)'
                        logger.info("Research v2 SUCCESS — using fallback intelligence.")
                    
                except Exception as e:
                    logger.error(f"Research v2 also failed: {e}")
                    genesis_response = None

            # ── Priority 6: Gemini Direct API Fallback ───────────────────
            # Both N8N paths failed. Instead of returning a dumb OFFLINE stub,
            # call Gemini 2.0 Flash directly with the market context.
            # 0 N8N executions consumed. Completely offline-proof.
            if not genesis_response or not isinstance(genesis_response, dict):
                genesis_response = self._gemini_direct_fallback(snapshot)

            elif 'n8n_live' not in genesis_response:
                genesis_response['n8n_live'] = True
                logger.info("Received Genesis Intelligence (LIVE).")

            # 3. SPX Event Poll (Independent of Genesis Research)
            # We call the secondary workflow for specific event data
            if not genesis_response.get('events') or len(genesis_response.get('events', [])) == 0:
                logger.info("Fetching SPX Events from dedicated micro-service...")
                
                # Dynamic Date Range Logic
                import datetime
                today = datetime.date.today()
                next_week = today + datetime.timedelta(days=7)
                date_query = f"SPX events {today.strftime('%b %d')} to {next_week.strftime('%b %d')} {today.year}"
                
                macro_url = "https://humanresource.app.n8n.cloud/webhook/alpha-macro-poll"
                spx_bridge = N8NBridge(webhook_url=macro_url)
                spx_events = spx_bridge.execute_workflow(payload={"query": date_query})
                
                if not spx_events:
                    # Fallback to test URL
                    logger.warning("Production macro webhook failed. Trying test webhook...")
                    test_url = macro_url.replace("/webhook/", "/webhook-test/")
                    spx_bridge = N8NBridge(webhook_url=test_url)
                    spx_events = spx_bridge.execute_workflow(payload={"query": date_query})
                
                # Robust Parsing for spx_events (Micro-service can also return 'text')
                if spx_events and isinstance(spx_events, dict) and 'text' in spx_events:
                    try:
                        raw_text = spx_events['text']
                        # Handle markdown and nested lists in text
                        json_match = re.search(r'\[.*\]', raw_text.replace('\n', ' '), re.DOTALL)
                        if json_match:
                            parsed_list = json.loads(json_match.group(0))
                            spx_events = parsed_list
                    except Exception as e:
                        logger.warning(f"Failed to parse micro-service text payload: {e}")

                if spx_events and isinstance(spx_events, list):
                    # Normalization: Map event_name -> event, impact_level -> impact
                    normalized = []
                    for e in spx_events:
                        normalized.append({
                            "event": e.get('event') or e.get('event_name') or "Unknown Event",
                            "impact": (e.get('impact') or e.get('impact_level') or "MED").upper(),
                            "days_until": e.get('days_until', 1) # Default to tomorrow if missing
                        })
                    genesis_response['events'] = normalized
                    logger.info(f"Merged {len(normalized)} normalized SPX events.")
                elif spx_events and isinstance(spx_events, dict) and 'events' in spx_events:
                    genesis_response['events'] = spx_events['events']
                    logger.info(f"Merged {len(spx_events['events'])} SPX events from dict.")
                if not genesis_response.get('events'):
                    logger.warning("Failed to retrieve SPX events from both Prod and Test. Attempting local cache fallback...")
                    try:
                        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                        event_file = os.path.join(project_root, "Alpha_Data", "upcoming_events.json")
                        if os.path.exists(event_file):
                            with open(event_file, 'r') as f:
                                cached_events = json.load(f)
                            if isinstance(cached_events, list):
                                # Re-normalize just in case
                                normalized = []
                                for e in cached_events:
                                    normalized.append({
                                        "event": e.get('event') or e.get('event_name') or "Unknown Event",
                                        "impact": (e.get('impact') or e.get('impact_level') or "MED").upper(),
                                        "days_until": e.get('days_until', 1)
                                    })
                                genesis_response['events'] = normalized
                                logger.info(f"Successfully recovered {len(normalized)} events from local cache.")
                    except Exception as cache_err:
                        logger.error(f"Local cache fallback failed: {cache_err}")

            return genesis_response
                
        except Exception as e:
            logger.error(f"External Commentary Fetch Failed: {e}")
            # Ensure we return something structured to avoid crashing the pipeline
            return {
                "forecast": "NEUTRAL",
                "commentary": f"System Error: {str(e)}",
                "risk_mode": "REDUCE_RISK",
                "events": []
            }

    # ══════════════════════════════════════════════════════════════════
    # Priority 6 — Gemini Direct API Fallback
    # ══════════════════════════════════════════════════════════════════
    def _gemini_direct_fallback(self, snapshot: dict) -> dict:
        """
        When BOTH N8N paths fail, calls Gemini 2.0 Flash directly via
        the Google AI Studio REST API.

        • 0 N8N executions consumed.
        • Uses the same GEMINI_API_KEY already stored in .env.
        • Returns the same structure as a successful N8N genesis response:
          { forecast, risk_mode, commentary, events, n8n_live, n8n_source }
        • If Gemini itself fails, falls back to the OFFLINE stub.
        """
        api_key = get_secret("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY not found in vault/.env — falling back to OFFLINE stub.")
            return self._offline_stub()

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

        system_prompt = (
            "You are the Lead Quant Architect for Alpha V2 Genesis, an SPX Iron Condor trading system. "
            "You will receive a market snapshot with SPX price, VIX level, IV rank, historical volatility, "
            "and recent trend data. Based on this data, provide a strategic assessment.\n\n"
            "RESPOND WITH VALID JSON ONLY. No markdown, no code fences, no explanation outside JSON.\n\n"
            "Required JSON structure:\n"
            "{\n"
            '  "forecast": "BULLISH" | "BEARISH" | "NEUTRAL",\n'
            '  "risk_mode": "REDUCE_RISK" | "HOLD_RISK" | "INCREASE_RISK",\n'
            '  "commentary": "2-3 sentence market analysis and strategic recommendation",\n'
            '  "confidence": 0.0 to 1.0,\n'
            '  "events": [\n'
            '    {"event": "Event Name", "date": "YYYY-MM-DD", "impact": "HIGH" | "MEDIUM" | "LOW",\n'
            '     "spx_impact": "Brief impact description"}\n'
            '  ]\n'
            "}"
        )

        user_prompt = (
            f"Market Snapshot (live data):\n"
            f"  SPX:             {snapshot.get('spx', 'N/A')}\n"
            f"  VIX:             {snapshot.get('vix', 'N/A')}\n"
            f"  IV Rank (30d):   {snapshot.get('iv_rank', 'N/A')}%\n"
            f"  HV (30d):        {snapshot.get('hv_30d', 'N/A')}%\n"
            f"  5-Day Trend:     {snapshot.get('trend_5d_pct', 'N/A')}%\n"
            f"  Date:            {datetime.now().strftime('%Y-%m-%d %H:%M EST')}\n\n"
            f"Provide your strategic assessment for the next 7 trading days."
        )

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": system_prompt + "\n\n" + user_prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 2048,
                "responseMimeType": "application/json",
            }
        }

        try:
            logger.info("Priority 6: Calling Gemini 2.0 Flash directly (N8N bypass)...")
            resp = requests.post(url, json=payload, timeout=30)

            if resp.status_code != 200:
                logger.warning(f"Gemini API returned {resp.status_code}: {resp.text[:200]}")
                return self._offline_stub()

            result = resp.json()
            raw_text = (
                result.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )

            # Strip markdown code fences if present
            clean = raw_text.strip()
            if clean.startswith("```"):
                clean = re.sub(r'^```(?:json)?\s*', '', clean)
                clean = re.sub(r'```\s*$', '', clean)

            parsed = json.loads(clean)

            # Validate required fields
            if "forecast" not in parsed:
                parsed["forecast"] = "NEUTRAL"
            if "risk_mode" not in parsed:
                parsed["risk_mode"] = "HOLD_RISK"
            if "commentary" not in parsed:
                parsed["commentary"] = "Gemini analysis received but commentary missing."
            if "events" not in parsed:
                parsed["events"] = []

            parsed["n8n_live"] = True       # Mark as "live intelligence" (not OFFLINE)
            parsed["n8n_source"] = "Gemini Direct (P6 Fallback)"

            logger.info(
                f"Gemini Direct SUCCESS — Forecast: {parsed['forecast']}, "
                f"Risk: {parsed['risk_mode']}, Confidence: {parsed.get('confidence', 'N/A')}"
            )
            return parsed

        except json.JSONDecodeError as e:
            logger.warning(f"Gemini returned non-JSON response: {e}")
            return self._offline_stub()
        except requests.exceptions.Timeout:
            logger.warning("Gemini API timed out after 20s.")
            return self._offline_stub()
        except Exception as e:
            logger.error(f"Gemini Direct fallback failed: {e}")
            return self._offline_stub()

    @staticmethod
    def _offline_stub() -> dict:
        """Last-resort stub when ALL intelligence sources are unavailable."""
        return {
            "forecast": "NEUTRAL",
            "commentary": "All intelligence sources offline (N8N + Gemini). Using local sensors only.",
            "risk_mode": "HOLD_RISK",
            "n8n_live": False,
            "n8n_source": "OFFLINE",
            "events": []
        }

    def generate_system_report(self, strategy_type, vix_level, delta_selection):
        """
        Generates the market_memo.md using the required template.
        """
        from datetime import datetime
        report = f"""# ALPHA ARCHITECT: SYSTEM RATIONALE
**Timestamp:** {datetime.now()}
**Recommended Strategy:** {strategy_type}

### Market Regime Analysis
* **VIX Level:** {vix_level}
* **Rationale:** {"Quiet market detected; favoring 7 DTE for rapid theta decay." if vix_level < 15 else "Volatility present; favoring 45 DTE for higher premium and safety margin."}

### Execution Parameters
* **Delta Range:** {delta_selection}
* **Management Rule:** {"CLOSE AT 21 DTE" if strategy_type == "45 DTE Core Income" else "CLOSE AT EXPIRATION/STOP"}
* **Profit Target:** 50% of Max Credit.

### Risk Warning
{"CAUTION: 0.20 Delta selected. Ensure strict 21 DTE exit to avoid Gamma exposure." if delta_selection >= 0.20 else "Standard risk profile active."}
"""
        # Save to disk
        # Save to disk
        # Fix: Alpha_V2_Genesis root is 3 levels up from skills/loki/loki.py
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        memo_path = os.path.join(project_root, "market_memo.md")
        try:
            with open(memo_path, "w") as f:
                f.write(report)
            logger.info(f"System Report generated at {memo_path}")
        except Exception as e:
            logger.error(f"Failed to save system report: {e}")
            
        return report

    def fetch_vertical_price(self, ticker_symbol, expiration, long_strike, short_strike, option_type="put"):
        try:
            chain = self.get_cached_chain(ticker_symbol, expiration)
            if not chain: return None
            
            df = chain.calls if option_type.lower() == "call" else chain.puts
            
            # Find Legs
            long_leg = df[df['strike'] == long_strike]
            short_leg = df[df['strike'] == short_strike]
            
            if long_leg.empty or short_leg.empty:
                logger.warning(f"Strike missing in chain {expiration}. L:{long_strike} S:{short_strike}")
                return None
                
            # Calculate Mark Price (Bid/Ask Average) if available, else Last
            def get_mark(row):
                bid = row['bid'].iloc[0]
                ask = row['ask'].iloc[0]
                last = row['lastPrice'].iloc[0]
                if bid > 0 and ask > 0:
                    return (bid + ask) / 2
                return last

            long_price = get_mark(long_leg)
            short_price = get_mark(short_leg)
            
            spread_mid = abs(short_price - long_price) 
            return round(spread_mid, 2)

        except Exception as e:
            logger.error(f"Option Fetch Error: {e}")
            return None

    def calculate_realtime_mmm(self, spx_price, expiration_date=None):
        try:
             if not expiration_date:
                 expiration_date = self.get_dynamic_expiration("^SPX", target_days=7) # Default to 7 days for MMM

             chain = self.get_cached_chain("^SPX", expiration_date)
             if not chain: return 103.016
             
             # Locate ATM Strike
             calls = chain.calls
             # Find strike closest to SPX
             atm_row = calls.iloc[(calls['strike'] - spx_price).abs().argsort()[:1]]
             if atm_row.empty:
                 return 103.016 
                 
             atm_strike = atm_row['strike'].values[0]
             
             # Get Straddle Price (Call Mark + Put Mark)
             c_row = calls[calls['strike'] == atm_strike]
             p_row = chain.puts[chain.puts['strike'] == atm_strike]
             
             def get_price(row):
                 if row.empty: return 0
                 return (row['bid'].values[0] + row['ask'].values[0]) / 2
                 
             straddle_price = get_price(c_row) + get_price(p_row)
             
             if straddle_price > 0:
                 return round(straddle_price, 2)
                 
             return 103.016
             
        except Exception as e:
            logger.error(f"MMM Calc Failed: {e}")
            return None # Do not use hardcoded fallback

    def evaluate_entry_criteria(self, snapshot, n8n_data):
        """
        New 'Hunting Mode' Logic:
        1. IV Rank > 50 (High Premiums)
        2. No Binary Events (Earnings/Fed) in next 3 days
        """
        iv_rank = snapshot.get('iv_rank', 0)
        
        # 1. IV Rank Check
        # Threshold lowered to 25% per Tactical Volatility Sentry protocol
        if iv_rank < 25:
            return {
                "action": "WAIT", 
                "rationale": f"Market Volatility too low (IV Rank: {iv_rank} < 25). WAITING FOR: IV Rank rise > 25 to ensure adequate premium collection."
            }
            
        # 2. Event Check (Parse N8N Commentary for Keywords)
        # Keywords that imply imminent binary events
        danger_keywords = ["earnings report", "fed meeting", "cpi release", "nfp release", "fomc", "jobs report", "gdp", "retail sales"]
        
        n8n_text = n8n_data.get('commentary', '').lower() if n8n_data else ""
        
        for keyword in danger_keywords:
            if keyword in n8n_text:
                 return {
                    "action": "WAIT",
                    "rationale": f"Event Risk Detected: '{keyword}'. WAITING FOR: Market stability after event passage."
                }
        
        return {
            "action": "ENTRY",
            "rationale": f"Hunting Mode Activated: High IV ({iv_rank}) + No Imminent Events detected."
        }

    def calculate_confidence_score(self, opinions):
        """
        Calculates a 0-100 Confidence Score based on Weighted Inputs:
        - Sentiment (30%)
        - Macro (25%)
        - Volatility (20%)
        - History (25%)
        """
        score = 0.0
        details = []
        
        # 1. Sentiment (30%)
        sent = opinions.get('sentiment', {})
        bias = sent.get('bias', 'NEUTRAL')
        if bias == 'BULLISH': score += 30
        elif bias == 'BEARISH': score += 0
        else: score += 15 # Neutral
        details.append(f"Sentiment: {bias} (+{15 if bias=='NEUTRAL' else (30 if bias=='BULLISH' else 0)})")

        # 2. Macro (25%)
        macro = opinions.get('macro', {})
        risk = macro.get('risk_level', 'LOW')
        if risk == 'LOW': score += 25
        elif risk == 'MEDIUM': score += 12.5
        else: score += 0
        details.append(f"Macro Risk: {risk} (+{0 if risk=='HIGH' else (12.5 if risk=='MEDIUM' else 25)})")

        # 3. Volatility (20%)
        # High IV Rank = Good for Credit Strategies = Higher Score
        # UNLESS n8n risk_score is high
        vol = opinions.get('volatility', {})
        iv_rank = vol.get('vix_rank_30d', 50)
        
        # Integrate n8n Risk Score if available (Weighted Synthesis)
        n8n_data = opinions.get('n8n') or {}
        n8n_risk_score = n8n_data.get('risk_score', 50) if isinstance(n8n_data, dict) else 50 # 0 to 100
        
        # If n8n risk is high, we lower the confidence in aggressive strategies
        safe_multi = max(0, (100 - n8n_risk_score) / 100)
        
        vol_score = (iv_rank / 100) * 20 * safe_multi
        score += vol_score
        details.append(f"Vol Rank: {iv_rank} (adj by Genesis Risk: {n8n_risk_score}) (+{round(vol_score,1)})")

        # 4. History (25%) - Mock
        # Assume history supports the Trade 70% of the time based on N8N
        hist_score = 25 * 0.7 
        score += hist_score
        details.append(f"History Match: 70% (+{hist_score})")
        
        return {
            "score": round(score, 1),
            "details": details
        }

    def determine_market_state(self, watchdog_report, active_trade):
        """
        Classifies environment into DANGER (Risk Mitigation) or STABLE (Profit Max).
        """
        if not active_trade:
            return "HUNTING"
            
        danger_side = watchdog_report.get('danger_side')
        status = watchdog_report.get('status', 'SAFE')
        
        # Danger Triggers: Only if status isn't SAFE
        if status != 'SAFE':
            return "DANGER"
            
        return "STABLE"

    def run_strategy(self, availability=2000):
        logger.info(f"Loki Awakens... (Availability: ${availability})")
        snapshot = self.get_market_snapshot()
        logger.info(f"Snapshot: {snapshot}")
        
        # 1. N8N Forecast (The Brain) - FETCH FIRST
        logger.info("Asking N8N for Strategic Forecast...")
        n8n_result = self.fetch_external_commentary()

        # 2. Gather Opinions (Driven by N8N if available)
        # Default Fallbacks
        sent_result = self.sentiment.analyze_headlines([]) 
        macro_result = self.macro.analyze_calendar()
        
        if n8n_result:
            # Overwrite Sentiment with Real N8N Data
            # Extract a snippet for the narrative
            full_commentary = n8n_result.get('commentary', '')
            narrative_snippet = (full_commentary[:100] + '...') if len(full_commentary) > 100 else full_commentary
            
            sent_result = {
                "bias": n8n_result.get('forecast', 'NEUTRAL'),
                "score": 0.0,
                "volatility_multiplier": 1.0,
                "narrative": narrative_snippet or "Driven by N8N Strategic Intelligence."
            }
            
            # Overwrite Macro Risk with N8N Risk Mode
            n8n_risk = n8n_result.get('risk_mode', 'REDUCE_RISK')
            macro_risk_level = "HIGH" if n8n_risk == 'REDUCE_RISK' else "LOW"
            
            # Use Macro Agent to process EVENTS if they exist
            n8n_events = n8n_result.get('events', [])
            macro_result = self.macro.analyze_calendar(n8n_events)
            
            # Force risk level if N8N explicitly requested REDUCE_RISK
            if macro_risk_level == "HIGH":
                macro_result['risk_level'] = "HIGH"
                
            macro_result['details'] = f"N8N Risk Mode: {n8n_risk} | Events: {len(n8n_events)}"
            
            # Persist Events to Alpha_Data
            try:
                # Use current file location as anchor
                # loki.py is in skills/loki/loki.py
                # root is 3 levels up: skills/loki -> skills -> Alpha_V2_Genesis
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                data_dir = os.path.join(project_root, "Alpha_Data")
                
                if not os.path.exists(data_dir):
                    os.makedirs(data_dir, exist_ok=True)
                event_file = os.path.join(data_dir, "upcoming_events.json")
                with open(event_file, "w") as f:
                    json.dump(n8n_events, f, indent=4)
                logger.info(f"Persisted {len(n8n_events)} events to {event_file}")
            except Exception as e:
                logger.error(f"Failed to persist events: {e}")
        
        # Watchdog (Defense)
        # Note: We rely on Default Portfolio data in Watchdog if not passed
        watchdog_report = self.watchdog.monitor_position(
            snapshot['spx'], 
            "STABLE", # volatility forecast simulation
            sent_result['bias']
        )
        
        # 3. Synthesize & Score
        expert_opinions = {
            "sentiment": sent_result,
            "watchdog": watchdog_report,
            "volatility": {"signal": "SELL", "vix_rank_30d": snapshot.get('iv_rank', 50), "forecast": "STABLE"}, 
            "macro": macro_result,
            "n8n": n8n_result
        }
        
        confidence = self.calculate_confidence_score(expert_opinions)
        logger.info(f"Alpha Confidence Score: {confidence['score']} ({confidence['details']})")

        # 4. Dual-Strategy Regime Switch (LOKI CORE)
        vix_level = snapshot.get('vix', 20.0)
        strategy_type = "7 DTE Tactical" if vix_level < 15 else "45 DTE Core Income"
        target_dte = 7 if vix_level < 15 else 45
        
        # Delta selection logic
        delta_selection = 0.15 # Default
        if strategy_type == "45 DTE Core Income":
            # If VIX > 15, prioritize 45 DTE with preference for 0.10 Delta if volatility is rising
            # Note: We check if VIX is higher than its 5d average for 'rising'
            vix_hist = snapshot.get('vix_hist_1y') # We might need to carry this from snapshot
            # For now, let's use a simpler check or assume 0.10 if VIX is elevated
            delta_selection = 0.10 if vix_level > 20 else 0.20
        
        active_trade = self.watchdog.load_portfolio()
        
        # --- VOLATILITY SENTRY: Persist IV Rank ---
        try:
             # Load, Update, Save
             # Use the path from the project structure instead of missing 'config' module
             script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
             p_path = os.path.join(script_dir, 'Alpha_Data', 'portfolio.json')
             
             if os.path.exists(p_path) and active_trade:
                 # Re-read to ensure we have full object (watchdog.load_portfolio might return dict)
                 with open(p_path, 'r') as f:
                     p_data = json.load(f)
                 
                 p_data['iv_rank_30d'] = snapshot.get('iv_rank', 0)
                 p_data['last_updated'] = str(datetime.datetime.now())
                 
                 with open(p_path, 'w') as f:
                     json.dump(p_data, f, indent=4)
                 logger.info(f"Volatility Sentry: Updated portfolio.json with IV Rank: {snapshot.get('iv_rank', 0)}%")
        except Exception as e:
             logger.error(f"Volatility Sentry Persistence Failed: {e}")
             
        market_state = self.determine_market_state(watchdog_report, active_trade)
        
        verdict = "WAIT"
        rationale = f"Market Scan Complete ({strategy_type}). Regime: {'Low' if vix_level < 15 else 'High'} Volatility."
        
        # Variables for Report
        target_short_put = 0
        target_long_put = 0
        current_short_put = active_trade.get('short_put_strike', 0) if active_trade else 0
        current_long_put = active_trade.get('long_put_strike', 0) if active_trade else 0
        hold_value = 0
        roll_value = 0
        
        # Dynamic Expiration Calculation based on Strategy
        target_exp = self.get_dynamic_expiration("^SPX", target_days=target_dte)
        
        if market_state == "HUNTING":
             # Hunt Logic
             hunt_result = self.evaluate_entry_criteria(snapshot, n8n_result)
             verdict = hunt_result['action']
             
             if verdict == "ENTRY":
                 # Implementation of Delta-based targeting
                 mid_strike = snapshot['spx']
                 # Simplified Delta-to-OTM distance for simulation (usually 10% for 0.10, 5% for 0.20)
                 distance_pct = 0.10 if delta_selection <= 0.15 else 0.05
                 
                 target_short_put = int(mid_strike * (1 - distance_pct) / 5) * 5
                 target_long_put = target_short_put - 20
                 rationale = f"Entry Signal for {strategy_type}. Target: {target_short_put}/{target_long_put}."
                 
                 # TRIGGER ALERT
                 play_alert_sound("success")
                 
        elif market_state == "DANGER":
             # Risk Mitigation Mode
             # Priority: Credit Roll > Least Debit Roll
             current_short_put = active_trade.get('short_put_strike', 6680)
             current_long_put = active_trade.get('long_put_strike', 6660)
             current_exp = active_trade.get('expiration_date')
             if not current_exp:
                 current_exp = self.get_dynamic_expiration("^SPX", target_days=7) # Default to 7 days for current exp
             
             # Calculate Hold Value (Cost to Close)
             hold_value = self.fetch_vertical_price("^SPX", current_exp, current_long_put, current_short_put, "put") or 0.1
             
             # Dynamic Defense Target
             # If Score > 50 (Bullish resilience), Roll Up 5pts. If Weak, Roll Down/Out.
             
             # Use the dynamically calculated target_exp from above
             # target_exp is already set to ~7-14 days out
             
             # Dynamic Strike Adjust
             # If High Confidence, we can roll UP (aggressive defense).
             strike_shift = 10 if confidence['score'] > 50 else -10
             target_short_put = current_short_put + strike_shift
             target_long_put = current_long_put + strike_shift
             
             roll_value = self.fetch_vertical_price("^SPX", target_exp, target_long_put, target_short_put, "put") or 0.1
             
             gate_status = "OPEN" if roll_value > hold_value else "CLOSED"
             
             if gate_status == "OPEN":
                 verdict = "ROLL (CREDIT)"
                 rationale = f"Risk Mitigation: Net Credit Roll possible (+${round(roll_value - hold_value, 2)}). Shifting strikes to follow trend."
             else:
                 # Check for "Least Debit"
                 debit = hold_value - roll_value
                 if debit < 0.50:
                     verdict = "ROLL (DEBIT)" # Pay to save
                     rationale = f"Risk Mitigation: Paying small debit (-${round(debit, 2)}) to extend duration and survive danger zone."
                 else:
                     verdict = "CLOSE" # Abort
                     rationale = f"Risk Mitigation: Roll too expensive (-${round(debit, 2)}). Hard Stop triggered to preserve capital."

        elif market_state == "STABLE":
            # Challenger Scan: Compare current position to a fresh target entry
            target_strike_dist = 0.10 if delta_selection <= 0.15 else 0.05
            challenger_dist_pct = round(target_strike_dist * 100, 2)
            current_dist_pct = watchdog_report.get('distance_pct', 0)
            if watchdog_report.get('status') == "PROFIT_TAKER":
                verdict = "CLOSE (PROFIT)"
                rationale = "Profit Target Reached (>50%). Banking gains."
            else:
                verdict = "HOLD"
                # Active scan comparison
                if current_dist_pct < (challenger_dist_pct * 0.6):
                     rationale = f"SCAN COMPLETE: Current trade is under-performing. Challenger Trade offers {challenger_dist_pct}% margin vs your {current_dist_pct}%. Suggesting ROLL if Credit increases."
                else:
                     rationale = f"SCAN COMPLETE: Current trade is OUT-PERFORMING challengers. Safety Margin: {current_dist_pct}% (Current) vs {challenger_dist_pct}% (Fresh Target). HOLDING."


        
        
        # MMM Calculation
        mmm_val = self.calculate_realtime_mmm(snapshot['spx'])
        
        logger.info(f"Live Pricing: Hold/Debit=${hold_value}, Roll/Credit=${roll_value}, MMM=${mmm_val}")
        
        # Defense logic
        expert_opinions['defense'] = {
            "financials": {
                "debit_close": hold_value,
                "credit_open": roll_value,
                "net_impact": round(roll_value - hold_value, 2),
                "width": "10 Wide", # Simplified
                "mmm": mmm_val
            },
            "target_trade": {
                "type": "Credit Put Vertical", # Assuming Put side management for now
                "short_put": target_short_put,
                "long_put": target_long_put,
                "expiration": target_exp
            },
            "details": f"Defense Matrix (Live Pricing: {current_short_put}/{current_long_put} -> {target_short_put}/{target_long_put})"
        }

        if n8n_result and 'forecast' in n8n_result:
             forecast = n8n_result.get('forecast', 'NEUTRAL')
             risk_mode = n8n_result.get('risk_mode', 'REDUCE_RISK')
             logger.info(f"N8N Strategic Forecast: {forecast} (Mode: {risk_mode})")
             
        # Phase 3: Mauro Gate Logic (Financial Check)
        # "Is it safe / profitable to roll?" - ONLY IF NOT HUNTING
        if market_state != "HUNTING":
            gate_status = "OPEN" if roll_value > hold_value else "CLOSED"
            
            gate_info = ""
            if gate_status == "OPEN":
                 gate_info = f"Mauro Risk Gate Open: Net Credit Roll available (${roll_value} > ${hold_value})."
                 if verdict == "HOLD":
                     verdict = "ROLL"
            else:
                 gate_info = f"Mauro Risk Gate Closed: Roll is Debit (-${round(hold_value - roll_value, 2)})."

            # Combine rationale to preserve Challenger Scan info
            rationale = f"{rationale} | {gate_info}"
                 
             # N8N Intelligence: Factor into rationale based on market state
            n8n_is_live = n8n_result.get('n8n_live', False) if n8n_result else False
            n8n_forecast = n8n_result.get('forecast', 'NEUTRAL') if n8n_result else 'NEUTRAL'
            n8n_risk_mode = n8n_result.get('risk_mode', 'HOLD_RISK') if n8n_result else 'HOLD_RISK'
            
            if n8n_is_live:
                # N8N is LIVE - include its intelligence in rationale
                if n8n_risk_mode == 'REDUCE_RISK' and market_state == 'DANGER' and verdict == 'HOLD':
                    # Only force defensive roll when Watchdog ALSO says position is in danger
                    if (hold_value - roll_value) < 0.50:
                        verdict = "ROLL (DEFENSIVE)"
                        rationale = f"N8N LIVE + Watchdog DANGER: Defensive Roll triggered (debit: ${round(hold_value - roll_value, 2)})."
                        play_alert_sound("danger")
                        show_popup("Alpha Defense", f"Defensive Roll Required!\nPayment: ${round(hold_value - roll_value, 2)}")
                else:
                    # N8N is live but position is STABLE - note advisory only
                    rationale = f"{rationale} | N8N: {n8n_forecast} ({n8n_risk_mode})"
            else:
                # N8N is in standby - note in rationale
                rationale = f"{rationale} | N8N: STANDBY (Local sensors only)"
        
        # 4. Risk Check
        proposal = {
            "action": verdict,
            "margin": 1000 # Mock
        }
        
        # Pass availability to Risk Agent (Margin Lock)
        risk_check = self.risk.evaluate_trade(proposal, {"vix": snapshot['vix'], "vix_rank": 50}, {"capital": 10000}, availability=availability)

        # Include N8N in System Report
        n8n_report_section = ""
        if n8n_result:
            # Check for commentary in n8n_result or parsed sub-fields
            commentary = n8n_result.get('commentary') or n8n_result.get('rationale') or "No details."
            n8n_report_section = f"\n\n## 🧠 Intelligence (N8N)\n- Forecast: {n8n_result.get('forecast', 'N/A')}\n- Directive: {n8n_result.get('risk_mode', 'N/A')}\n\n### Analysis\n{commentary}"

        n8n_is_live = n8n_result.get('n8n_live', False) if n8n_result else False
        n8n_source = n8n_result.get('n8n_source', 'Unknown') if n8n_result else 'OFFLINE'
        n8n_status_label = f"🟢 LIVE ({n8n_source})" if n8n_is_live else "🔴 STANDBY"
        
        final_decision = {
            "market_snapshot": snapshot,
            "expert_opinions": expert_opinions,
            "market_state": market_state,
            "n8n_status": n8n_status_label,
            "loki_proposal": {
                "strategy": verdict,
                "rationale": rationale,
                "confidence": confidence,
                "risk_score": n8n_result.get('risk_score', 50) if n8n_result else 50
            },
            "risk_check": risk_check,
            "hot_update_widgets": n8n_result.get('hot_update_widgets', []) if n8n_result else [],
            "final_action": verdict if risk_check['approved'] else "WAIT",
            "markdown_report": f"# System Report\n\n**Verdict**: {verdict}\n\n**Rationale**: {rationale}\n\n## N8N Intelligence ({n8n_status_label})\n- **SPX Risk Score**: {n8n_result.get('risk_score', 'N/A') if n8n_result else 'N/A'}/100\n- **Forecast**: {n8n_result.get('forecast', 'NEUTRAL') if n8n_result else 'NEUTRAL'}\n\n## Defense Logic\n- Hold Value: ${hold_value}\n- Roll Value: ${roll_value}\n- Net Impact: ${round(roll_value - hold_value, 2)}\n\n## Risk Check\n- Status: {'APPROVED' if risk_check['approved'] else 'VETOED'}\n- Reasons: {', '.join(risk_check.get('reasons', []))}{n8n_report_section}"
        }

        # 5. Push to n8n (Phase 4)
        logger.info("Pushing decision to Cloud...")
        try:
            push_decision(final_decision)
        except Exception as e:
            logger.error(f"Failed to push decision to N8N: {e}")
        
        # 6. Update Local Memo
        self.generate_analyst_memo(final_decision)
        
        logger.info("Loki decision complete.")
        return final_decision

if __name__ == "__main__":
    loki = Loki()
    print(loki.run_strategy())
