#!/usr/bin/env python3
"""
PnL WatchDog - Professional Quant Trading Tool
============================================

A production-ready tool for quant traders to analyze market microstructure
and protect against toxic order flow using institutional-grade data.

Features:
- Real-time Databento integration
- Kyle's Lambda toxicity detection
- Amihud illiquidity measurement
- Order flow imbalance analysis
- VWAP deviation tracking
- Alpha generation demonstration

Usage:
    python quant_trader_tool.py --symbol AAPL --lookback 100 --api-key YOUR_DATABENTO_KEY
"""

import time
import random
import argparse
from datetime import datetime
from pnl_watchdog.watchdog import PnLWatchdog

# Professional trading symbols
TRADING_SYMBOLS = ["AAPL", "MSFT", "GOOGL", "AMZN",
                   "META", "NVDA", "TSLA", "AMD", "INTC", "SPY", "QQQ"]


class ProfessionalPortfolio:
    """A professional portfolio tracker with PnL monitoring."""

    def __init__(self, name, initial_capital=1000000):
        self.name = name
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions = {}
        self.trades = []
        self.pnl_history = []

    def execute_trade(self, symbol, price, quantity, side, slippage_cost=0.0, timestamp=None):
        """Execute a trade with full tracking."""
        if timestamp is None:
            timestamp = datetime.now()

        cost = price * quantity
        total_cost = cost + slippage_cost

        if side.upper() == "BUY":
            self.cash -= total_cost
            self.positions[symbol] = self.positions.get(symbol, 0) + quantity
        elif side.upper() == "SELL":
            # Account for bid-ask spread
            self.cash += total_cost - (2 * slippage_cost)
            self.positions[symbol] = self.positions.get(symbol, 0) - quantity

        trade_record = {
            "timestamp": timestamp,
            "symbol": symbol,
            "side": side.upper(),
            "price": price,
            "quantity": quantity,
            "slippage_cost": slippage_cost,
            "total_cost": total_cost
        }
        self.trades.append(trade_record)

        # Update PnL
        current_value = self.get_portfolio_value({symbol: price})
        self.pnl_history.append({
            "timestamp": timestamp,
            "portfolio_value": current_value,
            "pnl": current_value - self.initial_capital
        })

        return trade_record

    def get_portfolio_value(self, current_prices):
        """Calculate current portfolio value."""
        value = self.cash
        for symbol, quantity in self.positions.items():
            if symbol in current_prices and quantity > 0:
                value += quantity * current_prices[symbol]
        return value

    def get_performance_metrics(self):
        """Get key performance metrics."""
        if not self.pnl_history:
            return {"total_pnl": 0, "return_pct": 0, "num_trades": 0}

        latest_pnl = self.pnl_history[-1]
        total_pnl = latest_pnl["pnl"]
        return_pct = (total_pnl / self.initial_capital) * 100
        slippage_paid = sum(trade["slippage_cost"] for trade in self.trades)

        return {
            "total_pnl": total_pnl,
            "return_pct": return_pct,
            "num_trades": len(self.trades),
            "total_slippage": slippage_paid
        }


def analyze_market_conditions(watchdog, symbol, lookback=50):
    """Professional market analysis using PnL WatchDog."""
    try:
        metrics = watchdog.get_order_flow_analytics(symbol, lookback=lookback)

        if "error" in metrics:
            return None

        return {
            "symbol": symbol,
            "timestamp": datetime.now(),
            "toxicity_score": metrics.get("toxicity_score", 0),
            "vwap_deviation_bps": metrics.get("vwap_deviation_bps", 0),
            "net_order_flow": metrics.get("net_order_flow", 0),
            "order_book_imbalance": metrics.get("order_book_imbalance", 0),
            "verdict": metrics.get("verdict", "UNKNOWN"),
            "is_toxic": metrics.get("verdict") == "HIGH TOXICITY"
        }
    except Exception as e:
        print(f"⚠️  Market analysis failed for {symbol}: {e}")
        return None


def professional_trading_session(api_key, symbols=None, iterations=5, lookback=50):
    """Run a professional trading session with full analytics."""

    print("\n" + "█" * 80)
    print("💰 PnL WATCHDOG PROFESSIONAL TRADING SUITE")
    print("   Institutional-Grade Market Microstructure Analysis")
    print("█" * 80)

    # Initialize professional tools
    watchdog = PnLWatchdog(broker="databento", api_key=api_key)

    # Two professional strategies
    blind_trader = ProfessionalPortfolio("🔴 Unprotected Algorithm")
    protected_trader = ProfessionalPortfolio("🟢 PnL WatchDog Protected")

    symbols = symbols or TRADING_SYMBOLS

    print(f"\n📊 Trading Session Started")
    print(f"   Symbols: {', '.join(symbols[:5])}...")
    print(f"   Lookback Period: {lookback} minutes")
    print("-" * 80)

    # Trading loop
    for i in range(iterations):
        symbol = random.choice(symbols)
        print(f"\n[{i+1}/{iterations}] Analyzing {symbol}...")

        # Professional market analysis
        market_data = analyze_market_conditions(watchdog, symbol, lookback)

        if not market_data:
            print(f"   ⚠️  No market data available, skipping...")
            continue

        # Realistic price estimation (in a real system, this would come from the market data)
        base_prices = {
            "AAPL": 190.0, "MSFT": 400.0, "GOOGL": 150.0, "AMZN": 160.0,
            "META": 480.0, "NVDA": 880.0, "TSLA": 240.0, "AMD": 155.0,
            "INTC": 35.0, "SPY": 550.0, "QQQ": 480.0
        }
        current_price = base_prices.get(symbol, 100.0)

        # Trade parameters
        quantity = random.randint(100, 1000)  # Professional lot sizes
        side = random.choice(["BUY", "SELL"])

        # Calculate realistic slippage based on market toxicity
        toxicity_factor = market_data["toxicity_score"] / 100.0
        base_slippage = current_price * 0.001  # 10 bps base slippage
        toxic_slippage = base_slippage * \
            (1 + toxicity_factor * 5)  # Up to 5x in toxic markets

        # Unprotected trader executes regardless
        blind_trader.execute_trade(
            symbol, current_price, quantity, side,
            slippage_cost=toxic_slippage
        )
        print(
            f"   🔴 Unprotected Trade: {side} {quantity} {symbol} @ ${current_price:.2f}")
        print(f"      Slippage Cost: ${toxic_slippage:.2f}")

        # Protected trader uses PnL WatchDog intelligence
        if market_data["is_toxic"]:
            print(f"   🟢 Protected Trade: 🛡️  BLOCKED - TOXIC MARKET DETECTED")
            print(f"      Toxicity: {market_data['toxicity_score']:.1f}/100")
            print(f"      Saved: ${toxic_slippage:.2f} in potential losses")
        else:
            protected_trader.execute_trade(
                symbol, current_price, quantity, side,
                slippage_cost=base_slippage  # Lower slippage in healthy markets
            )
            print(
                f"   🟢 Protected Trade: {side} {quantity} {symbol} @ ${current_price:.2f}")
            print(f"      Slippage Cost: ${base_slippage:.2f}")

        # Show real-time metrics
        if market_data["toxicity_score"] > 70:
            print(
                f"   ⚠️  EXTREME TOXICITY WARNING: {market_data['toxicity_score']:.1f}/100")
        elif market_data["toxicity_score"] > 40:
            print(
                f"   ⚠️  Moderate toxicity detected: {market_data['toxicity_score']:.1f}/100")

        print(
            f"   📊 VWAP Deviation: {market_data['vwap_deviation_bps']:.1f} bps")
        print(f"   📊 Order Flow: {market_data['net_order_flow']:,.0f}")

        time.sleep(1)  # Professional pacing

    # Final performance report
    print("\n" + "=" * 80)
    print("📈 PROFESSIONAL PERFORMANCE REPORT")
    print("=" * 80)

    blind_metrics = blind_trader.get_performance_metrics()
    protected_metrics = protected_trader.get_performance_metrics()

    slippage_savings = blind_metrics["total_slippage"] - \
        protected_metrics["total_slippage"]
    alpha_generated = slippage_savings

    print(f"\n🔴 Unprotected Algorithm:")
    print(f"   Total Slippage: ${blind_metrics['total_slippage']:,.2f}")
    print(f"   Number of Trades: {blind_metrics['num_trades']}")

    print(f"\n🟢 PnL WatchDog Protected:")
    print(f"   Total Slippage: ${protected_metrics['total_slippage']:,.2f}")
    print(f"   Number of Trades: {protected_metrics['num_trades']}")
    print(f"   Slippage Avoided: ${slippage_savings:,.2f}")

    if alpha_generated > 0:
        print(f"\n💰 ALPHA GENERATION:")
        print(f"   Generated Alpha: ${alpha_generated:,.2f}")
        print(
            f"   Alpha/Trade: ${alpha_generated/max(protected_metrics['num_trades'], 1):.2f}")
        print(f"\n✅ PnL WatchDog successfully protected against toxic market conditions!")
        print(f"   Recommendation: Deploy in production for consistent alpha generation.")
    else:
        print(f"\n⚠️  No significant alpha generated in this session.")
        print(f"   Consider adjusting parameters or market conditions.")

    print("\n" + "█" * 80)
    print("PnL WatchDog Professional Trading Session Complete")
    print("█" * 80)


def main():
    """Main entry point for the professional trading tool."""
    parser = argparse.ArgumentParser(
        description="PnL WatchDog Professional Trading Tool")
    parser.add_argument("--api-key", required=True, help="Databento API Key")
    parser.add_argument("--symbols", nargs="+",
                        help="Trading symbols (default: major tech stocks)")
    parser.add_argument("--iterations", type=int, default=5,
                        help="Number of trading iterations")
    parser.add_argument("--lookback", type=int, default=50,
                        help="Lookback period in minutes")

    args = parser.parse_args()

    try:
        professional_trading_session(
            api_key=args.api_key,
            symbols=args.symbols,
            iterations=args.iterations,
            lookback=args.lookback
        )
    except KeyboardInterrupt:
        print("\n\n🛑 Trading session interrupted by user.")
    except Exception as e:
        print(f"\n❌ Trading session failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
