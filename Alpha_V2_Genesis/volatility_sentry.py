import yfinance as yf
import time
import logging
import os
import sys

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - VolSentry - %(levelname)s - %(message)s')
logger = logging.getLogger("Sentry")

def monitor_vix():
    logger.info("🛡️ Volatility Sentry Armed. Monitoring ^VIX...")
    last_vix = None
    
    while True:
        try:
            vix_data = yf.Ticker("^VIX").history(period="1d")
            if not vix_data.empty:
                current_vix = vix_data['Close'].iloc[-1]
                
                if last_vix is not None:
                    change = current_vix - last_vix
                    if change > 1.0:
                        logger.warning(f"⚠️ VOLATILITY SPIKE: VIX jumped +{change:.2f} to {current_vix:.2f}")
                        # In a real environment, this would trigger an alert sound or popup
                
                logger.info(f"VIX Level: {current_vix:.2f}")
                last_vix = current_vix
        except Exception as e:
            logger.error(f"Sentry Error: {e}")
            
        time.sleep(300) # Check every 5 minutes

if __name__ == "__main__":
    monitor_vix()
