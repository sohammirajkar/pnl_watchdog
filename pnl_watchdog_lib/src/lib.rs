use pyo3::prelude::*;

/// Calculates Amihud Illiquidity and Kyle's Lambda in one pass.
#[pyfunction]
fn calculate_whale_metrics(
    opens: Vec<f64>,
    closes: Vec<f64>,
    volumes: Vec<f64>,
) -> PyResult<(f64, f64)> {
    let len = opens.len();
    let mut returns_abs = Vec::with_capacity(len);
    let mut dollar_vols = Vec::with_capacity(len);
    let mut signed_vols = Vec::with_capacity(len);
    let mut price_changes = Vec::with_capacity(len);

    for i in 0..len {
        if volumes[i] <= 0.0 {
            continue;
        }

        let ret = (closes[i] - opens[i]) / opens[i];
        let dollar_vol = closes[i] * volumes[i];
        returns_abs.push(ret.abs());
        dollar_vols.push(dollar_vol);

        let sign = if closes[i] >= opens[i] { 1.0 } else { -1.0 };
        signed_vols.push(volumes[i] * sign);
        price_changes.push(closes[i] - opens[i]);
    }

    let amihud_score = if !dollar_vols.is_empty() {
        let sum_ratio: f64 = returns_abs
            .iter()
            .zip(&dollar_vols)
            .map(|(r, v)| r / v)
            .sum();
        (sum_ratio / dollar_vols.len() as f64) * 1_000_000.0
    } else {
        0.0
    };

    let kyles_lambda = if signed_vols.len() > 1 {
        let n = signed_vols.len() as f64;
        let sum_x: f64 = signed_vols.iter().sum();
        let sum_y: f64 = price_changes.iter().sum();
        let sum_xy: f64 = signed_vols
            .iter()
            .zip(&price_changes)
            .map(|(x, y)| x * y)
            .sum();
        let sum_xx: f64 = signed_vols.iter().map(|x| x * x).sum();

        let numerator = n * sum_xy - sum_x * sum_y;
        let denominator = n * sum_xx - sum_x * sum_x;

        if denominator.abs() > 1e-9 {
            (numerator / denominator) * 1_000_000.0
        } else {
            0.0
        }
    } else {
        0.0
    };

    Ok((amihud_score, kyles_lambda))
}

/// Order Flow Metrics: VWAP, Toxicity, Net Order Flow, OBI
/// Returns: (vwap_deviation_bps, toxicity, net_order_flow, order_book_imbalance, vwap_price)
#[pyfunction]
fn calculate_order_flow_metrics(
    prices: Vec<f64>,
    volumes: Vec<f64>,
    bid_prices: Vec<f64>,
    ask_prices: Vec<f64>,
) -> PyResult<(f64, f64, f64, f64, f64)> {
    let len = prices.len();
    if len == 0 {
        return Ok((0.0, 0.0, 0.0, 0.0, 0.0));
    }

    // 1. VWAP
    let sum_pv: f64 = prices.iter().zip(&volumes).map(|(p, v)| p * v).sum();
    let sum_v: f64 = volumes.iter().sum();
    let vwap = if sum_v > 0.0 { sum_pv / sum_v } else { 0.0 };

    // 2. VWAP Deviation (Basis Points)
    let last_price = prices[len - 1];
    let vwap_dev = if vwap > 0.0 {
        ((last_price - vwap).abs() / vwap) * 10000.0
    } else {
        0.0
    };

    // 3. Net Order Flow (Buying vs Selling Pressure)
    let avg_price: f64 = prices.iter().sum::<f64>() / len as f64;
    let nof: f64 = prices
        .iter()
        .zip(&volumes)
        .map(|(p, v)| if *p > avg_price { *v } else { -*v })
        .sum();

    // 4. Toxicity & Imbalance (Using Snapshot of Bids/Asks)
    // Note: In a real stream, these vectors would be time-aligned.
    // Here we calculate the aggregate imbalance of the provided snapshots.
    let (toxicity, obi) = if !bid_prices.is_empty() && !ask_prices.is_empty() {
        let best_bid = bid_prices.iter().cloned().fold(0. / 0., f64::max);
        let best_ask = ask_prices.iter().cloned().fold(0. / 0., f64::min);
        let midprice = (best_bid + best_ask) / 2.0;

        // Simple Toxicity Proxy: Distance of VWAP from Midprice relative to Spread
        let spread = best_ask - best_bid;
        let tox = if spread > 0.0 {
            ((vwap - midprice).abs() / spread) * 100.0
        } else {
            0.0
        };

        // Order Book Imbalance (Volume weighted if we had depth, simple count here)
        let bid_count = bid_prices.len() as f64;
        let ask_count = ask_prices.len() as f64;
        let imbalance = (bid_count - ask_count) / (bid_count + ask_count + 0.001);

        (tox, imbalance)
    } else {
        (0.0, 0.0)
    };

    Ok((vwap_dev, toxicity, nof, obi, vwap))
}

#[pymodule]
fn pnl_watchdog(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(calculate_whale_metrics, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_order_flow_metrics, m)?)?;
    Ok(())
}
