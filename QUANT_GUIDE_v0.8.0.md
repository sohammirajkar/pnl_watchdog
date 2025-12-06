# 📘 Quant Trader's Guide to PnL Watchdog v0.8.0

## Overview
PnL Watchdog v0.8.0 is a **Cross-Market Execution Intelligence** system designed to minimize implementation shortfall and detect market regime changes in real-time. It combines high-performance Rust micro-kernels with a flexible Python SDK.

---

## 🧩 Core Modules Explained

### 1. Dynamic Execution Alpha Model (New in v0.8.0)
**Rust Module**: `calculate_dynamic_execution_params`
**Concept**: Traditional Almgren-Chriss models are static. This module makes execution dynamic by incorporating your **Alpha Signal** (edge).
- **Logic**: If you have a strong alpha signal (high predicted return), the system automatically increases urgency to capture the move before it decays, overriding standard risk aversion.
- **Formula**: $\text{Effective Risk Aversion} \approx \gamma \times (1 - \tanh(\text{Alpha} \times \text{Sensitivity}))$

### 2. Asset-Specific Lambda Engine
**Rust Module**: `calculate_kyle_lambda_asset_specific`
**Concept**: Market impact varies wildly between asset classes. A 100-lot order means something very different in Apple vs. Bitcoin vs. Euro Futures.
- **Adaptation**:
  - **Equities**: Standard square-root law.
  - **Futures**: Adds a "Tick Size Continuity" correction for discrete pricing.
  - **Crypto**: Multiplies volatility by 2.5x and assumes shallower depth.
  - **Prediction Markets**: Assumes extremely shallow books (1% depth factor).

### 3. Jump Risk Estimator (Regime Detection)
**Rust Module**: `calculate_jump_risk`
**Concept**: Financial returns are not Gaussian. "Fat tails" (crashes) happen far more often than a Normal distribution predicts.
- **Method**: Merton Jump-Diffusion Model.
- **Output**:
  - **Jump Probability**: The likelihood that the current price action is driven by a discontinuous "jump" rather than normal diffusion.
  - **Intensity**: How violent the jumps are relative to normal volatility.

---

## 🚀 How to Use This Tool

### Scenario A: The "Alpha Capture" Trade
**Goal**: You have a predictive signal (e.g., ML model predicts AAPL up 0.5% in 10 mins) and need to enter a 5,000 share position.

```python
# 1. Get the Plan
plan = dog.get_dynamic_execution_plan(
    symbol="AAPL",
    asset_class="EQUITIES",
    total_qty=5000,
    alpha_signal=0.05,  # Strong 5% signal strength
    base_risk_aversion=0.5
)

# 2. Execute
slice_size = plan['recommended_slice']
# Result: System might recommend trading 100% (5000 shares) NOW because the Alpha is strong 
# and outweighs the market impact cost.
```

### Scenario B: The "Risk-Off" Monitor
**Goal**: You run a crypto market-making bot and want to pause if the market becomes unstable (crash risk).

```python
# 1. Check Regime
regime = dog.get_market_regime("BTC/USDT")

# 2. Act
if regime['metrics']['jump_probability'] > 0.15: # >15% probability of jumps
    print("⚠️ CRASH RISK DETECTED! Halting Market Maker.")
    bot.pause_trading()
```

### Scenario C: HFT Signal Streaming
**Goal**: You have a C++ execution engine and want to feed it real-time Lambda costs from Python.

```python
# Stream Lambda to localhost port 5000
dog.stream_lambda("FUTURES", lambda_value=0.59, ip="127.0.0.1", port=5000)
```

---

## 📊 Interpretation of Results

| Metric | Low Value | High Value | Implication |
| :--- | :--- | :--- | :--- |
| **Lambda** | < 0.1 | > 1.0 | High Lambda = High Slippage. Trade smaller/slower. |
| **Jump Prob** | < 1% | > 10% | High Prob = Market is breaking. Widen spreads or exit. |
| **Alpha Signal** | 0.0 | > 0.1 | High Alpha = Trade Faster (Urgency). |

## 🏁 Conclusion
PnL Watchdog v0.8.0 transforms you from a "blind" price taker into a **strategic liquidity consumer**. It tells you **when** to be aggressive (High Alpha) and **when** to be passive (High Lambda/Jump Risk).
