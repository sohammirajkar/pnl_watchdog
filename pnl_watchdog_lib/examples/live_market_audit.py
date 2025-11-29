import os
import sys
import time
import random
import statistics
import numpy as np
from datetime import datetime, timedelta
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
import databento as db

# --- CONFIG ---
# ⚠️ REPLACE WITH REAL KEYS FOR THE SCREENSHOT
# Use your real Alpaca Key (e.g., Paper Trading key)
ALPACA_KEY = "PKPELYDWCZ6RM4ODQDP4YPOA3N"
# Use your real Alpaca Secret
ALPACA_SECRET = "8WXEeSd9wa3NJKNxrDDk7WSCeBN6Ef9NNh7cceKR9JNG"
# Use your real Databento Key (starts with db-)
DATABENTO_KEY = "db-4YkcnL9CbMJwsD8Uh7vvSfgUYuHqr"

# The "Controversial" Tickers
SYMBOLS = ["AAPL", "GME"]  # Keeping it focused for the stress test


class MarketAuditor:
    def __init__(self):
        self.alpaca = StockHistoricalDataClient(ALPACA_KEY, ALPACA_SECRET)
        self.db = db.Historical(key=DATABENTO_KEY)

    def get_metrics_at_time(self, symbol, target_end_time):
        """
        Fetches Retail vs Institutional metrics for a specific historical window.
        Window size: 2 hours ending at target_end_time.
        """
        start_dt = target_end_time - timedelta(hours=2)

        # 1. Fetch Retail (Alpaca)
        retail_score = 0.0
        try:
            req = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Minute,
                start=start_dt,
                end=target_end_time,
                limit=1000
            )
            bars = self.alpaca.get_stock_bars(req)
            retail_score = self._calculate_metrics(bars[symbol])
        except Exception as e:
            # print(f"   [Alpaca Error]: {e}")
            pass

        # 2. Fetch Institutional (Databento)
        inst_score = 0.0
        try:
            data = self.db.timeseries.get_range(
                dataset='XNAS.ITCH',
                symbols=symbol,
                schema='ohlcv-1m',
                stype_in='raw_symbol',
                start=start_dt.isoformat(),
                end=target_end_time.isoformat()
            )
            df = data.to_df()
            candles = [{"close": r['close'], "open": r['open'],
                        "volume": r['volume']} for i, r in df.iterrows()]
            inst_score = self._calculate_metrics(candles)
        except Exception as e:
            # print(f"   [Databento Error]: {e}")
            pass

        return retail_score, inst_score

    def _calculate_metrics(self, candles):
        price_changes = []
        signed_vols = []

        for c in candles:
            # Handle object vs dict access
            close_p = c.close if hasattr(c, 'close') else c['close']
            open_p = c.open if hasattr(c, 'open') else c['open']
            vol = c.volume if hasattr(c, 'volume') else c['volume']

            if vol == 0:
                continue

            change = close_p - open_p
            sign = 1 if change >= 0 else -1

            price_changes.append(change)
            signed_vols.append(vol * sign)

        # Kyle's Lambda
        if len(signed_vols) > 1:
            slope, _ = np.polyfit(signed_vols, price_changes, 1)
            return slope * 1_000_000
        return 0.0


def run_monte_carlo_audit():
    auditor = MarketAuditor()
    print("\n" + "█"*60)
    print(f"🎲 PnL WATCHDOG: MONTE CARLO FAIRNESS AUDIT")
    print(f"   Sampling random windows over last 30 days to remove bias.")
    print("█"*60 + "\n")

    # Generate 5 random trading timestamps from the last 30 days
    # (Avoiding weekends roughly)
    samples = []
    for _ in range(5):
        # Start from T-2 to avoid live license
        days_ago = random.randint(2, 30)
        # Ensure we pick a weekday (0=Mon, 4=Fri)
        date_candidate = datetime.now() - timedelta(days=days_ago)
        while date_candidate.weekday() > 4:
            date_candidate -= timedelta(days=1)

        # Pick a random time during trading hours (10 AM - 3 PM ET approx)
        # This avoids pre-market noise
        random_hour = random.randint(15, 20)  # Converted to UTC roughly
        final_dt = date_candidate.replace(
            hour=random_hour, minute=0, second=0, microsecond=0)
        samples.append(final_dt)

    for sym in SYMBOLS:
        print(
            f"Analyzing {sym} across {len(samples)} random historical points...")
        gaps = []

        for sample_time in samples:
            r_score, i_score = auditor.get_metrics_at_time(sym, sample_time)

            # Skip empty data points (e.g. holidays)
            if r_score == 0 and i_score == 0:
                continue

            gap_pct = abs(i_score - r_score) / (r_score + 0.00001) * 100
            gaps.append(gap_pct)

            print(
                f"   📅 {sample_time.strftime('%Y-%m-%d %H:%M')} | Retail: {r_score:.4f} | Inst: {i_score:.4f} | Gap: {gap_pct:.1f}%")

        if gaps:
            avg_gap = statistics.mean(gaps)
            print(f"\n   📉 AVERAGE STRUCTURAL BLINDNESS: {avg_gap:.1f}%")
            if avg_gap > 50:
                print(
                    f"   ❌ VERDICT: Systematic Disadvantage. This asset is permanently fragmented.")
            else:
                print(f"   ✅ VERDICT: Fair Market. Retail sees what Institutions see.")
        else:
            print("   ⚠️ No valid data points found (Check Holiday/Weekend logic).")

        print("-" * 40)


if __name__ == "__main__":
    run_monte_carlo_audit()
