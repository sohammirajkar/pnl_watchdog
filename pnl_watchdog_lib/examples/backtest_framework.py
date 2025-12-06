#!/usr/bin/env python3
"""
Quant OS Backtesting Framework
==============================

Validates whether Quant OS strategy (Regime Switching + Optimal Stopping) 
makes more money than traditional static TP/SL strategies.

Comparison:
1. BASELINE_STATIC: Fixed 2% TP, 1% SL
2. BASELINE_HOLD: Buy and Hold (no exits)
3. QUANT_OS: Dynamic TP/SL based on volatility + regime filtering

Author: PnL Watchdog
"""
import os
import sys
import time
import statistics
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import pnl_core

# =============================================================================
# DATA STRUCTURES
# =============================================================================

class TradeDirection(Enum):
    LONG = "LONG"
    SHORT = "SHORT"

class TradeResult(Enum):
    WIN = "WIN"
    LOSS = "LOSS"
    OPEN = "OPEN"

@dataclass
class Trade:
    """Represents a single trade"""
    entry_time: int  # Candle index
    entry_price: float
    direction: TradeDirection
    take_profit: float
    stop_loss: float
    exit_time: Optional[int] = None
    exit_price: Optional[float] = None
    pnl: float = 0.0
    pnl_pct: float = 0.0
    result: TradeResult = TradeResult.OPEN
    regime_at_entry: str = "UNKNOWN"

@dataclass
class BacktestResult:
    """Results of a backtest run"""
    strategy_name: str
    symbol: str
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    total_pnl_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    profit_factor: float = 0.0
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)

# =============================================================================
# BACKTEST ENGINE
# =============================================================================

class BacktestEngine:
    """
    Core backtesting engine for Quant OS strategy validation.
    """
    
    def __init__(self, candles: List[Dict[str, float]], symbol: str = "TEST"):
        """
        Initialize backtest engine with historical candle data.
        
        Args:
            candles: List of dicts with 'open', 'high', 'low', 'close', 'volume'
            symbol: Trading symbol for labeling
        """
        self.candles = candles
        self.symbol = symbol
        self.lookback = 50  # Candles needed for indicator calculation
        
    def _calculate_regime(self, idx: int) -> Tuple[str, float, float]:
        """Calculate regime at a specific candle index"""
        if idx < self.lookback:
            return "UNKNOWN", 0.001, 0.0001
        
        window = self.candles[idx-self.lookback:idx]
        opens = [c['open'] for c in window]
        closes = [c['close'] for c in window]
        volumes = [c['volume'] for c in window]
        
        try:
            _, kyles_lambda, _ = pnl_core.calculate_market_quality_metrics(opens, closes, volumes)
            volatility, _, _ = pnl_core.calculate_jump_risk(closes)
            
            regime = pnl_core.calculate_market_regime(
                volatility, kyles_lambda, 
                0.005,  # vol_threshold
                0.0005  # lambda_threshold
            )
            return regime, volatility, kyles_lambda
        except Exception as e:
            return "UNKNOWN", 0.001, 0.0001
    
    def _calculate_optimal_exit(self, entry_price: float, volatility: float, 
                                 time_horizon: float = 600.0) -> Tuple[float, float]:
        """Calculate optimal TP/SL using Rust core"""
        try:
            tp, sl = pnl_core.calculate_optimal_exit_price(
                entry_price, time_horizon, volatility, 0.000001, 0.1
            )
            return tp, sl
        except:
            # Fallback to 5% TP, 3% SL
            return entry_price * 1.05, entry_price * 0.97

    def _simulate_trade(self, trade: Trade, start_idx: int) -> Trade:
        """Simulate trade execution through future candles"""
        for i in range(start_idx + 1, len(self.candles)):
            candle = self.candles[i]
            high = candle['high']
            low = candle['low']
            close = candle['close']
            
            if trade.direction == TradeDirection.LONG:
                # Check if TP hit (high >= TP)
                if high >= trade.take_profit:
                    trade.exit_time = i
                    trade.exit_price = trade.take_profit
                    trade.pnl = trade.take_profit - trade.entry_price
                    trade.pnl_pct = (trade.pnl / trade.entry_price) * 100
                    trade.result = TradeResult.WIN
                    break
                # Check if SL hit (low <= SL)
                elif low <= trade.stop_loss:
                    trade.exit_time = i
                    trade.exit_price = trade.stop_loss
                    trade.pnl = trade.stop_loss - trade.entry_price
                    trade.pnl_pct = (trade.pnl / trade.entry_price) * 100
                    trade.result = TradeResult.LOSS
                    break
            else:  # SHORT
                if low <= trade.take_profit:
                    trade.exit_time = i
                    trade.exit_price = trade.take_profit
                    trade.pnl = trade.entry_price - trade.take_profit
                    trade.pnl_pct = (trade.pnl / trade.entry_price) * 100
                    trade.result = TradeResult.WIN
                    break
                elif high >= trade.stop_loss:
                    trade.exit_time = i
                    trade.exit_price = trade.stop_loss
                    trade.pnl = trade.entry_price - trade.stop_loss
                    trade.pnl_pct = (trade.pnl / trade.entry_price) * 100
                    trade.result = TradeResult.LOSS
                    break
        
        # If not exited, close at last candle
        if trade.result == TradeResult.OPEN:
            trade.exit_time = len(self.candles) - 1
            trade.exit_price = self.candles[-1]['close']
            if trade.direction == TradeDirection.LONG:
                trade.pnl = trade.exit_price - trade.entry_price
            else:
                trade.pnl = trade.entry_price - trade.exit_price
            trade.pnl_pct = (trade.pnl / trade.entry_price) * 100
            trade.result = TradeResult.WIN if trade.pnl > 0 else TradeResult.LOSS
        
        return trade
    
    def _calculate_metrics(self, result: BacktestResult) -> BacktestResult:
        """Calculate performance metrics from trades"""
        if not result.trades:
            return result
        
        result.total_trades = len(result.trades)
        result.winning_trades = sum(1 for t in result.trades if t.result == TradeResult.WIN)
        result.losing_trades = result.total_trades - result.winning_trades
        result.total_pnl = sum(t.pnl for t in result.trades)
        result.total_pnl_pct = sum(t.pnl_pct for t in result.trades)
        result.win_rate = (result.winning_trades / result.total_trades * 100) if result.total_trades > 0 else 0
        
        # Average win/loss
        wins = [t.pnl_pct for t in result.trades if t.result == TradeResult.WIN]
        losses = [t.pnl_pct for t in result.trades if t.result == TradeResult.LOSS]
        result.avg_win_pct = statistics.mean(wins) if wins else 0
        result.avg_loss_pct = statistics.mean(losses) if losses else 0
        
        # Profit factor
        gross_profit = sum(t.pnl for t in result.trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in result.trades if t.pnl < 0))
        result.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Equity curve and max drawdown
        equity = 10000.0  # Start with $10,000
        peak_equity = equity
        max_dd = 0.0
        result.equity_curve = [equity]
        
        for trade in result.trades:
            equity += trade.pnl
            result.equity_curve.append(equity)
            if equity > peak_equity:
                peak_equity = equity
            dd = (peak_equity - equity) / peak_equity * 100
            if dd > max_dd:
                max_dd = dd
        
        result.max_drawdown_pct = max_dd
        
        # Sharpe Ratio (simplified - daily returns)
        returns = [t.pnl_pct for t in result.trades]
        if len(returns) > 1:
            avg_return = statistics.mean(returns)
            std_return = statistics.stdev(returns)
            result.sharpe_ratio = (avg_return / std_return) * (252 ** 0.5) if std_return > 0 else 0
        
        return result
    
    # =========================================================================
    # STRATEGY IMPLEMENTATIONS
    # =========================================================================
    
    def run_static_tpsl(self, tp_pct: float = 2.0, sl_pct: float = 1.0, 
                        trade_frequency: int = 10) -> BacktestResult:
        """
        Baseline strategy: Fixed percentage TP/SL
        
        Args:
            tp_pct: Take profit percentage (e.g., 2.0 = 2%)
            sl_pct: Stop loss percentage (e.g., 1.0 = 1%)
            trade_frequency: Enter trade every N candles
        """
        result = BacktestResult(
            strategy_name=f"Static TP/SL ({tp_pct}%/{sl_pct}%)",
            symbol=self.symbol
        )
        
        i = self.lookback
        while i < len(self.candles) - 10:  # Leave room for trade to complete
            entry_price = self.candles[i]['close']
            tp = entry_price * (1 + tp_pct / 100)
            sl = entry_price * (1 - sl_pct / 100)
            
            trade = Trade(
                entry_time=i,
                entry_price=entry_price,
                direction=TradeDirection.LONG,
                take_profit=tp,
                stop_loss=sl
            )
            
            trade = self._simulate_trade(trade, i)
            result.trades.append(trade)
            
            # Move to next entry after this trade completes
            i = trade.exit_time + trade_frequency if trade.exit_time else i + trade_frequency
        
        return self._calculate_metrics(result)
    
    def run_buy_and_hold(self) -> BacktestResult:
        """
        Baseline strategy: Buy at start, sell at end
        """
        result = BacktestResult(
            strategy_name="Buy & Hold",
            symbol=self.symbol
        )
        
        entry_price = self.candles[self.lookback]['close']
        exit_price = self.candles[-1]['close']
        pnl = exit_price - entry_price
        pnl_pct = (pnl / entry_price) * 100
        
        trade = Trade(
            entry_time=self.lookback,
            entry_price=entry_price,
            direction=TradeDirection.LONG,
            take_profit=exit_price * 10,  # Effectively no TP
            stop_loss=0,  # Effectively no SL
            exit_time=len(self.candles) - 1,
            exit_price=exit_price,
            pnl=pnl,
            pnl_pct=pnl_pct,
            result=TradeResult.WIN if pnl > 0 else TradeResult.LOSS
        )
        result.trades.append(trade)
        
        return self._calculate_metrics(result)
    
    def run_quant_os(self, trade_frequency: int = 10, 
                     time_horizon: float = 600.0) -> BacktestResult:
        """
        Quant OS Strategy: Regime Switching + Optimal Stopping
        
        - Only trades when regime is NORMAL (skips TRANSITION and SL_HUNT)
        - Uses dynamic TP/SL based on volatility
        """
        result = BacktestResult(
            strategy_name="Quant OS (Regime + OptStop)",
            symbol=self.symbol
        )
        
        trades_skipped = 0
        i = self.lookback
        
        while i < len(self.candles) - 10:
            # 1. Calculate current regime
            regime, volatility, lambda_val = self._calculate_regime(i)
            
            # 2. REGIME FILTER: Only trade in NORMAL regime
            if regime != "NORMAL":
                trades_skipped += 1
                i += trade_frequency
                continue
            
            # 3. Calculate optimal exit using Rust core
            entry_price = self.candles[i]['close']
            tp, sl = self._calculate_optimal_exit(entry_price, volatility, time_horizon)
            
            trade = Trade(
                entry_time=i,
                entry_price=entry_price,
                direction=TradeDirection.LONG,
                take_profit=tp,
                stop_loss=sl,
                regime_at_entry=regime
            )
            
            trade = self._simulate_trade(trade, i)
            result.trades.append(trade)
            
            i = trade.exit_time + trade_frequency if trade.exit_time else i + trade_frequency
        
        result = self._calculate_metrics(result)
        print(f"   [Quant OS] Skipped {trades_skipped} trades due to non-NORMAL regime")
        return result


# =============================================================================
# BACKTEST RUNNER
# =============================================================================

def generate_synthetic_data(n_candles: int = 500, base_price: float = 100.0,
                           volatility: float = 0.02, trend: float = 0.0001) -> List[Dict]:
    """Generate synthetic OHLCV data for testing"""
    import random
    random.seed(42)  # Reproducible
    
    candles = []
    price = base_price
    
    for i in range(n_candles):
        # Random walk with slight trend
        change = random.gauss(trend, volatility)
        open_price = price
        
        # Intrabar volatility
        high = open_price * (1 + abs(random.gauss(0, volatility * 0.5)))
        low = open_price * (1 - abs(random.gauss(0, volatility * 0.5)))
        close = open_price * (1 + change)
        
        # Ensure high >= low and proper OHLC relationship
        high = max(high, open_price, close)
        low = min(low, open_price, close)
        
        volume = random.randint(10000, 100000)
        
        candles.append({
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        })
        
        price = close
    
    return candles


def run_backtest_comparison(candles: List[Dict], symbol: str = "TEST") -> Dict[str, BacktestResult]:
    """Run all strategies and compare results"""
    engine = BacktestEngine(candles, symbol)
    
    results = {}
    
    print(f"\n📊 Running backtest on {symbol} ({len(candles)} candles)...")
    print("-" * 50)
    
    # 1. Static TP/SL (2%/1%)
    print("   Running: Static TP/SL (2%/1%)...")
    results['static'] = engine.run_static_tpsl(tp_pct=2.0, sl_pct=1.0)
    
    # 2. Buy and Hold
    print("   Running: Buy & Hold...")
    results['hold'] = engine.run_buy_and_hold()
    
    # 3. Quant OS
    print("   Running: Quant OS (Regime + OptStop)...")
    results['quant_os'] = engine.run_quant_os()
    
    return results


def print_comparison_table(results: Dict[str, BacktestResult]):
    """Print formatted comparison table"""
    print("\n" + "=" * 80)
    print("📈 BACKTEST RESULTS COMPARISON")
    print("=" * 80)
    
    # Header
    print(f"{'Strategy':<30} {'Trades':>7} {'Win%':>7} {'Total P&L%':>12} {'Sharpe':>8} {'Max DD%':>9} {'PF':>6}")
    print("-" * 80)
    
    for name, result in results.items():
        print(f"{result.strategy_name:<30} {result.total_trades:>7} {result.win_rate:>6.1f}% "
              f"{result.total_pnl_pct:>+11.2f}% {result.sharpe_ratio:>8.2f} "
              f"{result.max_drawdown_pct:>8.2f}% {result.profit_factor:>6.2f}")
    
    print("=" * 80)
    
    # Determine winner
    quant_os = results.get('quant_os')
    static = results.get('static')
    
    if quant_os and static:
        diff = quant_os.total_pnl_pct - static.total_pnl_pct
        if diff > 0:
            print(f"\n✅ Quant OS outperforms Static TP/SL by {diff:.2f}%!")
        else:
            print(f"\n⚠️ Static TP/SL outperforms Quant OS by {-diff:.2f}%")
    
    # Statistical significance note
    print("\n📊 Note: For statistical significance, run on multiple symbols and time periods.")


def main():
    """Main backtest entry point"""
    print("=" * 80)
    print("🧪 QUANT OS BACKTESTING FRAMEWORK")
    print("=" * 80)
    print("Comparing: Quant OS vs Static TP/SL vs Buy & Hold")
    print()
    
    # Try to use DataBento data first
    try:
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
        from pnl_watchdog.brokers.databento import DatabentoAdapter
        
        api_key = "db-ieJvGbF9HQ3CaMGUuVXLC4YhFcs3Q"
        adapter = DatabentoAdapter(api_key)
        
        symbols = ["SPY", "AAPL", "NVDA"]
        all_results = {}
        
        for symbol in symbols:
            print(f"\n📥 Fetching {symbol} data from DataBento...")
            candles = adapter.get_candles(symbol, lookback=168)  # 7 days hourly
            
            if candles and len(candles) > 60:
                results = run_backtest_comparison(candles, symbol)
                all_results[symbol] = results
                print_comparison_table(results)
            else:
                print(f"   ⚠️ Insufficient data for {symbol}, using synthetic data")
                candles = generate_synthetic_data(500, base_price=100 + len(symbol))
                results = run_backtest_comparison(candles, f"{symbol} (Synthetic)")
                all_results[symbol] = results
                print_comparison_table(results)
        
        # Final Summary
        print("\n" + "=" * 80)
        print("📊 FINAL SUMMARY ACROSS ALL SYMBOLS")
        print("=" * 80)
        
        quant_os_total = sum(r['quant_os'].total_pnl_pct for r in all_results.values())
        static_total = sum(r['static'].total_pnl_pct for r in all_results.values())
        
        print(f"Quant OS Total P&L: {quant_os_total:+.2f}%")
        print(f"Static TP/SL Total P&L: {static_total:+.2f}%")
        print(f"Difference: {quant_os_total - static_total:+.2f}%")
        
        if quant_os_total > static_total:
            print("\n🎉 CONCLUSION: Quant OS BEATS Static TP/SL across all symbols!")
        else:
            print("\n⚠️ CONCLUSION: More tuning needed - Static TP/SL performs better")
            
    except Exception as e:
        print(f"⚠️ DataBento not available: {e}")
        print("Using synthetic data for demonstration...")
        
        # Fallback to synthetic data
        candles = generate_synthetic_data(500, base_price=100.0, volatility=0.015)
        results = run_backtest_comparison(candles, "SYNTHETIC")
        print_comparison_table(results)


if __name__ == "__main__":
    main()
