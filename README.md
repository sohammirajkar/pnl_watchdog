OLD:

# 🐶 PnL Watchdog

**Stop losing money to silent failures.**

Every quant has been there: Your bot logs say `Order Filled`, but your broker API timed outand you are actually flat. You don't find out until market close.

`pnl-watchdog` is a lightweight Python library that double-checks your broker's ledgerimmediately after your bot trades. If the trade is missing, it alerts you.

---

NEW:

# 🐶 PnL Watchdog: Infrastructure Economics Advisor

**Measure the hidden cost of your execution. Optimize your strategy within broker constraints.**

Your broker shows you a filled order at price X. But did you get the same X that institutions get?

**No.** You're paying a latency tax. Every single trade.

`pnl-watchdog` measures **Kyle's Lambda fairness gaps** between retail and institutional execution.Then it shows you exactly how much that gap costs you—and how to trade profitably within it.

**Stop fighting latency. Start optimizing around it.**

---