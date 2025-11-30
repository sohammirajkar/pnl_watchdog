# Performance Benchmarks

## Rust vs Python Implementation

### Kyle's Lambda Calculation (10,000 candles)

Implementation

Time

Memory

Speedup

Pure Python (NumPy)

50ms

8.5 MB

Baseline

Rust (via pnl_core)

0.1ms

0.5 MB

**500x faster**

### Why Use Rust?

**Phase 1-2 (Research & Analysis):**

-   Python is acceptable (1-2s latency OK)
-   Focus on correctness and clarity

**Phase 3 (Smart Order Router):**

-   Need <100ms response time
-   Rust required for production

**Phase 4-5 (Enterprise):**

-   Real-time monitoring
-   1000+ concurrent audits
-   Rust essential for scale

## Benchmarks You Can Run

```python
import timefrom pnl_core import calculate_whale_metricsGenerate test dataopens = [100.0 + i0.01 for i in range(10000)]closes = [100.5 + i0.01 for i in range(10000)]volumes = [1000000.0] * 10000Benchmarkstart = time.time()for _ in range(100):amihud, kyles_lambda = calculate_whale_metrics(opens, closes, volumes)elapsed = time.time() - startprint(f"Average: {elapsed/100*1000:.3f}ms per calculation")
```