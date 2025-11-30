# 🐶 PnL Watchdog: Infrastructure Economics Advisor

**Measure the hidden cost of your execution. Optimize your strategy within broker constraints.**

Your broker shows you filled orders. But are you getting the same prices as institutions?

**No.** You're paying a latency tax. Every single trade.

pnl-watchdog measures **Kyle's Lambda fairness gaps** between retail and institutional execution using **Rust-accelerated calculations**—then shows you exactly how much that gap costs you and how to trade profitably within it.

**Stop fighting latency. Start optimizing around it.**

## 🚀 Key Features

- **Kyle's Lambda Calculator**: Measure price impact per signed volume (Rust-accelerated)
- **Fairness Audit**: Compare retail vs institutional execution costs
- **AI Anomaly Detection**: Catch unusual latency/slippage patterns
- **Smart Order Routing**: Get broker recommendations based on real-time performance
- **Privacy First**: No strategy exposure—only anonymous telemetry

## ⚡ Performance: Powered by Rust

| Operation | Rust | Python | Speedup |
|-----------|------|--------|---------|
| Kyle's Lambda (10k candles) | 0.1ms | 50ms | **500x faster** |
| Fairness Audit (5 samples) | 100ms | 1-2s | **20x faster** |
| Batch Processing (1000 symbols) | 100ms | 50s | **500x faster** |

## 📦 Installation

```bash
pip install pnl-watchdog
```

## 🎯 Quick Start

```python
from pnl_watchdog import PnLWatchdog

# Initialize with your broker credentials
dog = PnLWatchdog(
    broker="alpaca",
    api_key="YOUR_API_KEY",
    api_secret="YOUR_SECRET_KEY"
)

# Verify a trade
result = dog.check_order("AAPL", "buy", 10)
print(f"Trade verified in {result['latency_ms']}ms")

# Calculate Kyle's Lambda for market analysis
from pnl_watchdog import calculate_whale_metrics

opens = [100.0, 101.0, 102.0, 101.5, 100.5]
closes = [101.0, 102.0, 101.5, 100.5, 101.0]
volumes = [1000.0, 2000.0, 1500.0, 500.0, 1200.0]

amihud, kyles_lambda = calculate_whale_metrics(opens, closes, volumes)
print(f"Kyle's Lambda: {kyles_lambda}")
```

## 📊 Advanced Analytics

```python
# Get institutional order flow metrics
from pnl_watchdog import calculate_order_flow_metrics

prices = [100.0, 101.0, 102.0, 101.5, 100.5]
volumes = [1000.0, 2000.0, 1500.0, 500.0, 1200.0]
bids = [99.9, 100.9, 101.9, 101.4, 100.4]
asks = [100.1, 101.1, 102.1, 101.6, 100.6]

vwap_dev, tox, nof, obi, vwap = calculate_order_flow_metrics(prices, volumes, bids, asks)
print(f"Toxicity Score: {tox}")
print(f"VWAP: {vwap}")
```

## 🤝 Supported Brokers

- Alpaca
- Interactive Brokers
- Binance (and other CCXT-supported exchanges)
- Zerodha
- Angel One

## 📚 Documentation

- [Infrastructure Economics Guide](https://github.com/sohammirajkar/pnl_watchdog/blob/main/docs/ECONOMICS.md)
- [Performance Benchmarks](https://github.com/sohammirajkar/pnl_watchdog/blob/main/docs/PERFORMANCE.md)
- [API Reference](https://github.com/sohammirajkar/pnl_watchdog/wiki)

## 📞 Support

For issues, feature requests, or questions, please [open an issue](https://github.com/sohammirajkar/pnl_watchdog/issues) on GitHub.
