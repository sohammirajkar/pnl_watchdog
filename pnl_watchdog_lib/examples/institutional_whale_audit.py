
# --- CONFIG ---
from pnl_watchdog import PnLWatchdog
import databento as db
from alpaca.data.timeframe import TimeFrame
from alpaca.data.requests import StockBarsRequest
from alpaca.data.historical import StockHistoricalDataClient
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

ALPACA_KEY = "PKQHZMESZIUWFLJYSZ6JSE3Q2Y"
ALPACA_SECRET = "6NFCA5xH1GzuFFGetEwGBTJbjfdGEN19mnZ27xMuUXqU"
DATABENTO_KEY = "db-vpXFYPPUBepXcA3YBftXQdGUjNyrL"


# SYMBOL TO TEST
SYMBOL = "AAPL"

# --- CRITICAL FIX: SYNC TIME WINDOWS ---
# We anchor both tests to 24 hours ago to ensure Databento data is finalized.
# This ensures a fair "Apples to Apples" comparison.
ANCHOR_TIME = datetime.now() - timedelta(days=1)

# --- ADAPTER 1: ALPACA (Retail Feed) ---


class AlpacaFeed:
    def __init__(self, key, secret):
        self.client = StockHistoricalDataClient(key, secret)

    def get_candles(self, symbol, lookback):
        print(
            f"   [Alpaca] Fetching 100 hours ending {ANCHOR_TIME.strftime('%Y-%m-%d %H:%M')}...")

        # Start time is Lookback hours before the Anchor
        start_dt = ANCHOR_TIME - timedelta(hours=lookback)

        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Hour,
            start=start_dt,
            end=ANCHOR_TIME,  # Explicit End Time
            limit=lookback
        )
        try:
            bars = self.client.get_stock_bars(req)
            return [{"open": b.open, "close": b.close, "volume": b.volume} for b in bars[symbol]]
        except Exception as e:
            print(f"   [Alpaca Error] {e}")
            return []

# --- ADAPTER 2: DATABENTO (Institutional Feed) ---


class DatabentoFeed:
    def __init__(self, key):
        self.client = db.Historical(key=key)

    def get_candles(self, symbol, lookback):
        print(f"   [Databento] Fetching high-fidelity history for {symbol}...")
        try:
            # Calculate exact start/end to match Alpaca
            start_dt = ANCHOR_TIME - timedelta(hours=lookback)

            data = self.client.timeseries.get_range(
                dataset='XNAS.ITCH',  # NASDAQ TotalView
                symbols=symbol,
                schema='ohlcv-1h',
                stype_in='raw_symbol',
                start=start_dt.isoformat(),
                end=ANCHOR_TIME.isoformat()  # Fixed End Time
            )

            # Convert DataFrame to list of dicts
            df = data.to_df()
            candles = []
            for index, row in df.iterrows():
                candles.append({
                    "open": row['open'],
                    "close": row['close'],
                    "volume": row['volume']
                })
            return candles

        except Exception as e:
            print(f"   [Databento Error] {e}")
            return []


# --- THE SHOWDOWN ---
print("\n" + "="*60)
print(f"🐋 PnL WATCHDOG: RETAIL VS INSTITUTIONAL DATA AUDIT")
print("="*60)

# Initialize Dog
dog = PnLWatchdog(broker="audit_mode")

# 1. TEST ALPACA
print("\n[1] Analyzing RETAIL Feed (Alpaca/SIP)...")
dog.broker = AlpacaFeed(ALPACA_KEY, ALPACA_SECRET)
res_retail = dog.get_whale_view(SYMBOL, lookback_candles=100)

print(f"   -> Amihud (Cost): {res_retail.get('amihud_illiquidity', 0)}")
print(f"   -> Kyle's Lambda: {res_retail.get('kyles_lambda', 0)}")
print(f"   -> Verdict: {res_retail.get('verdict')}")

# 2. TEST DATABENTO
print("\n[2] Analyzing INSTITUTIONAL Feed (Databento/TotalView)...")
dog.broker = DatabentoFeed(DATABENTO_KEY)
res_inst = dog.get_whale_view(SYMBOL, lookback_candles=100)

if res_inst.get('error'):
    print(f"   -> Skipped: {res_inst['error']}")
else:
    print(f"   -> Amihud (Cost): {res_inst.get('amihud_illiquidity', 0)}")
    print(f"   -> Kyle's Lambda: {res_inst.get('kyles_lambda', 0)}")
    print(f"   -> Verdict: {res_inst.get('verdict')}")

# THE COMPARISON
if not res_inst.get('error'):
    # Calculate absolute difference
    diff_lambda = abs(res_retail['kyles_lambda'] - res_inst['kyles_lambda'])
    diff_amihud = abs(
        res_retail['amihud_illiquidity'] - res_inst['amihud_illiquidity'])

    print("\n" + "-"*60)
    print(f"📊 DATA QUALITY AUDIT (Comparison)")
    print(f"   Gap in Insider Detection (Lambda): {diff_lambda:.6f}")
    print(f"   Gap in Liquidity Cost (Amihud):    {diff_amihud:.6f}")

    if diff_lambda > 0.05:
        print("\n⚠️  WARNING: Retail feed is missing significant Whale Activity.")
        print("   Smart Money is hiding in the noise that SIP feeds filter out.")
    else:
        print("\n✅  STATUS: Retail feed is accurately tracking Smart Money.")
    print("="*60 + "\n")
