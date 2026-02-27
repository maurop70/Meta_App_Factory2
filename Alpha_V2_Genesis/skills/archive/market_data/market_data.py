import yfinance as yf
import pandas as pd
import time
from functools import lru_cache
import logging

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MarketDataSkill")

class MarketDataAgent:
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 60 # seconds

    def _get_ticker(self, symbol):
        """Helper to get yfinance Ticker object."""
        return yf.Ticker(symbol)

    def fetch_current_price(self, symbol):
        """Fetches the latest available price."""
        try:
            ticker = self._get_ticker(symbol)
            # Try fast fetch via history (1m)
            df = ticker.history(period="1d", interval="1m")
            if not df.empty:
                return df['Close'].iloc[-1]
            
            # Fallback to daily
            df_daily = ticker.history(period="5d", interval="1d")
            if not df_daily.empty:
                return df_daily['Close'].iloc[-1]
                
            logger.error(f"No price data found for {symbol}")
            return None
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            return None

    @lru_cache(maxsize=32)
    def fetch_history(self, symbol, period="1mo", interval="1d"):
        """Fetches historical OHLCV data. Cached."""
        try:
            ticker = self._get_ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            if df.empty:
                logger.warning(f"Empty history for {symbol}")
            return df
        except Exception as e:
            logger.error(f"Error fetching history for {symbol}: {e}")
            return pd.DataFrame()

    def fetch_volatility_index(self):
        """Specialized fetch for VIX."""
        return self.fetch_current_price("^VIX")

    def fetch_news(self, symbol="SPY"):
        """Fetches recent news via a liquid proxy (default SPY for SPX)."""
        try:
            ticker = self._get_ticker(symbol)
            return ticker.news
        except Exception as e:
            logger.error(f"Error fetching news for {symbol}: {e}")
            return []

    def get_expiration_dates(self, symbol="^SPX"):
        """Fetches available option expiration dates."""
        try:
            ticker = self._get_ticker(symbol)
            return ticker.options
        except Exception as e:
            logger.error(f"Error fetching options for {symbol}: {e}")
            return []

    def get_option_chain(self, symbol="^SPX", date=None):
        """Fetches option chain for a specific date."""
        try:
            ticker = self._get_ticker(symbol)
            if not date:
                date = ticker.options[0] # Default to nearest
            return ticker.option_chain(date)
        except Exception as e:
            logger.error(f"Error fetching chain for {symbol} on {date}: {e}")
            return None

    def get_option_price(self, symbol, expiration, strike, option_type="call"):
        """
        Fetches the Bid/Ask/Last for a specific option.
        option_type: 'call' or 'put'
        """
        try:
            chain = self.get_option_chain(symbol, expiration)
            if chain is None: return None
            
            df = chain.calls if option_type.lower() == "call" else chain.puts
            
            # Find closest strike (exact match preferred)
            row = df[df['strike'] == strike]
            if row.empty:
                logger.warning(f"Strike {strike} not found for {expiration}")
                return None
            
            data = row.iloc[0]
            price = {
                "bid": data.get('bid', 0.0),
                "ask": data.get('ask', 0.0),
                "last": data.get('lastPrice', 0.0),
                "volume": data.get('volume', 0)
            }
            # Fallback if bid/ask are 0 (illiquid or closed market), use last
            if price['bid'] == 0 and price['last'] > 0:
                price['bid'] = price['last']
            if price['ask'] == 0 and price['last'] > 0:
                price['ask'] = price['last']
                
            return price
        except Exception as e:
            logger.error(f"Error pricing option {symbol} {expiration} {strike}: {e}")
            return None

    def get_market_snapshot(self):
        """High-level summary of the market state."""
        spx_price = self.fetch_current_price("^SPX")
        vix_price = self.fetch_volatility_index()
        news = self.fetch_news("SPY")
        
        # Calculate recent trend (5-day return)
        history = self.fetch_history("^SPX", period="5d")
        if not history.empty and spx_price is not None:
            start_price = history['Close'].iloc[0]
            trend_pct = ((spx_price - start_price) / start_price) * 100
        else:
            trend_pct = 0.0

        return {
            "timestamp": time.time(),
            "spx": spx_price,
            "vix": vix_price,
            "trend_5d_pct": round(trend_pct, 2),
            "news_count": len(news)
        }

if __name__ == "__main__":
    # Self-Test
    agent = MarketDataAgent()
    print("... Testing Senses ...")
    snapshot = agent.get_market_snapshot()
    print(f"Snapshot: {snapshot}")
