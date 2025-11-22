# 🐶 PnL Watchdog

**Stop losing money to silent failures.**

Every quant has been there: Your bot logs say `Order Filled`, but your broker API timed out and you are actually flat. You don't find out until market close.

`pnl-watchdog` is a lightweight Python library that double-checks your broker's ledger immediately after your bot trades. If the trade is missing, it alerts you.

### Installation
```bash
pip install pnl-watchdog