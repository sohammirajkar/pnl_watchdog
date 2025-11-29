use pyo3::prelude::*;

/// Calculates Amihud Illiquidity and Kyle's Lambda in one pass.
/// Returns: (amihud_score, kyles_lambda)
#[pyfunction]
fn calculate_whale_metrics(
    opens: Vec<f64>,
    closes: Vec<f64>,
    volumes: Vec<f64>,
) -> PyResult<(f64, f64)> {
    let len = opens.len();
    let mut returns_abs = Vec::with_capacity(len);
    let mut dollar_vols = Vec::with_capacity(len);

    // Vectors for Linear Regression (Kyle's Lambda)
    let mut signed_vols = Vec::with_capacity(len); // X
    let mut price_changes = Vec::with_capacity(len); // Y

    // 1. Single Pass Loop (O(n))
    for i in 0..len {
        if volumes[i] <= 0.0 {
            continue;
        }

        // Amihud Logic
        let ret = (closes[i] - opens[i]) / opens[i];
        let dollar_vol = closes[i] * volumes[i];

        returns_abs.push(ret.abs());
        dollar_vols.push(dollar_vol);

        // Kyle's Lambda Logic (Proxy: Close > Open means Buy)
        let sign = if closes[i] >= opens[i] { 1.0 } else { -1.0 };
        signed_vols.push(volumes[i] * sign);
        price_changes.push(closes[i] - opens[i]);
    }

    // 2. Calculate Amihud (Mean of |Ret| / $Vol)
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

    // 3. Calculate Kyle's Lambda (Slope of Linear Regression)
    // Formula: slope = (N * Σxy - Σx * Σy) / (N * Σx² - (Σx)²)
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

/// The Python Module Definition (Updated for PyO3 0.21+)
#[pymodule]
fn pnl_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(calculate_whale_metrics, m)?)?;
    Ok(())
}
