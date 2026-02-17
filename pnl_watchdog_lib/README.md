# PnL Watchdog for Crypto Market Makers

PnL Watchdog is a read-only execution intelligence layer for market makers on crypto venues like Bybit.

It helps you answer one question fast: `is my edge being eaten by microstructure friction?`

## Why it is useful

- Measures execution friction (impact, slippage, toxicity proxies, order-flow quality)
- Flags anomaly windows where fills degrade (latency/slippage outliers)
- Gives user-scoped import + analytics from your own account history
- Works with read-only exchange credentials (no trade/withdraw permissions required)

## 5-minute setup

1. Start API:

```bash
uvicorn pnl_watchdog_lib.api.main:app --host 0.0.0.0 --port 8000
```

2. Register your PnL Watchdog API key:

```bash
curl -X POST http://localhost:8000/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com"}'
```

3. Import Bybit read-only trade history:

```bash
curl -X POST http://localhost:8000/import/bybit \
  -H "Content-Type: application/json" \
  -H "X-API-Key: pnlw_your_key" \
  -d '{"api_key":"BYBIT_READ_KEY","api_secret":"BYBIT_READ_SECRET","market_type":"swap","lookback_days":7}'
```

4. Get your execution stats:

```bash
curl -X GET http://localhost:8000/stats/pnl \
  -H "X-API-Key: pnlw_your_key"
```

## Security model

- Use exchange keys with `read-only` scope only.
- PnL Watchdog API keys are stored hashed at rest.
- Data is scoped per authenticated user.
