use pyo3::prelude::*;
use std::time::{SystemTime, UNIX_EPOCH};
use std::net::UdpSocket;

// ==========================================
// MODULE 0: CORE CONSTANTS & CONFIGURATION
// ==========================================

/// Maximum safe Kyle's Lambda (price change per unit volume) we tolerate before halting execution.
/// A value like 0.0001 (1bp/unit) is a common high-risk threshold. 
/// Setting this high for testing but recommending a review based on asset class.
const MAX_SAFE_LAMBDA: f64 = 0.01; 

/// Market configuration struct for asset-specific pricing models.
struct MarketConfig {
    tick_size: f64,
    vol_multiplier: f64,
    depth_factor: f64, // Factor applied to order_size to determine effective market depth consumed
}

impl MarketConfig {
    /// Provides customized microstructure parameters based on asset class.
    fn get_config(asset_class: &str) -> Self {
        match asset_class.to_uppercase().as_str() {
            "EQUITIES" => MarketConfig { tick_size: 0.01, vol_multiplier: 1.0, depth_factor: 1.0 },
            "FUTURES" => MarketConfig { tick_size: 0.25, vol_multiplier: 0.8, depth_factor: 1.5 },
            "FX" => MarketConfig { tick_size: 0.00005, vol_multiplier: 1.5, depth_factor: 0.5 },
            "CRYPTO" => MarketConfig { tick_size: 0.00001, vol_multiplier: 2.5, depth_factor: 0.1 }, 
            "COMMODITIES" => MarketConfig { tick_size: 0.01, vol_multiplier: 1.2, depth_factor: 0.75 }, 
            "ENERGY" => MarketConfig { tick_size: 0.01, vol_multiplier: 1.8, depth_factor: 0.5 },
            "PREDICTION_MARKETS" => MarketConfig { tick_size: 0.01, vol_multiplier: 3.0, depth_factor: 0.01 }, 
            _ => MarketConfig { tick_size: 0.01, vol_multiplier: 1.0, depth_factor: 1.0 },
        }
    }
}


// ==========================================
// MODULE 9: TRANSACTION COST MODEL (TCM) FILTER
// ==========================================

/// Implements the Transaction Cost Model (TCM) pre-trade filter logic.
/// HARDENED: Now includes Liquidity Score as a mandatory GATING FACTOR.
#[pyfunction]
fn calculate_pre_trade_pnl_filter(
    alpha_pnl: f64,           // Expected PnL from the Alpha signal (in currency)
    asset_specific_lambda: f64, // Kyle's Lambda (Market Impact per unit quantity)
    total_qty: f64,           // Total order quantity (not sliced)
    brokerage_rate: f64,      // Fixed fee or percentage commission rate
    liquidity_score: f64,     // TCM Liquidity Score (e.g., from 0 to 100)
    min_liquidity_threshold: f64, // Minimum required liquidity score (e.g., 20.0)
) -> PyResult<bool> {
    
    // 1. LIQUIDITY GATE: If liquidity is toxic (score is too low), halt immediately.
    let liquidity_safe = liquidity_score >= min_liquidity_threshold;
    if !liquidity_safe {
        println!("[TCM Filter] HALT: Liquidity Score ({:.1}) below threshold ({:.1}).", liquidity_score, min_liquidity_threshold);
        return Ok(false); 
    }

    // 2. Calculate Estimated Market Impact Cost (Lambda * Qty)
    let market_impact_cost = asset_specific_lambda * total_qty;

    // 3. Calculate Estimated Fixed Brokerage Cost
    let fixed_brokerage_cost = brokerage_rate;

    // 4. Calculate Total Predicted Transaction Cost
    let total_transaction_cost = market_impact_cost + fixed_brokerage_cost;

    // 5. Apply the PnL filter: Only trade if expected PnL > Total Cost
    let trade_profitable = alpha_pnl > total_transaction_cost;

    println!(
        "[TCM Filter] PnL: {:.4}, Cost: {:.6} (Impact: {:.6}, Brokerage: {:.2}) -> Trade: {}",
        alpha_pnl, total_transaction_cost, market_impact_cost, fixed_brokerage_cost, trade_profitable
    );

    Ok(trade_profitable)
}


// ==========================================
// MODULE 8: DYNAMIC EXECUTION ALPHA MODEL (WITH COLLAR)
// ==========================================

/// Combines an Alpha signal with microstructure costs (Lambda, Volatility)
/// to dynamically calculate the optimal execution urgency, slice size, and **Protective Collar**.
/// 
/// HARDENED: Execution is now extremely sensitive to high Lambda values.
/// Returns: (Optimal Slice Size, Effective Risk Aversion (Gamma), Protective Collar)
#[pyfunction]
fn calculate_dynamic_execution_params(
    alpha_signal: f64,
    total_qty: f64,
    volatility: f64,
    lambda: f64, // Lambda should be in price/unit (e.g., USD/Share)
    base_risk_aversion: f64,
    alpha_sensitivity: f64,
) -> PyResult<(f64, f64, f64)> { 
    // Safety checks
    if total_qty <= 0.0 || volatility <= 0.0 || base_risk_aversion <= 0.0 || lambda <= 1e-9 {
        return Ok((0.0, base_risk_aversion, 0.0005));
    }

    // 1. IMMEDIATE LAMBDA HARD STOP (Addressing the 8.5 problem)
    // If the Lambda is unreasonably high (toxic market impact), we halt execution.
    if lambda > MAX_SAFE_LAMBDA {
        println!("[EXECUTION] HALT: Lambda ({:.6}) exceeds MAX_SAFE_LAMBDA ({:.6})", lambda, MAX_SAFE_LAMBDA);
        return Ok((0.0, base_risk_aversion, 999.0)); // Slice size 0.0, large collar as warning
    }

    // 2. Dynamic Risk Aversion Adjustment (Gamma)
    let alpha_tanh = (alpha_signal * alpha_sensitivity).tanh();
    
    // Higher Alpha -> Lower Effective Gamma (less risk averse, faster execution)
    let risk_multiplier = 1.0 - alpha_tanh.max(-0.9).min(0.9); // Clamp multiplier
    let effective_gamma = (base_risk_aversion * risk_multiplier)
        .max(0.01) // Minimum risk aversion
        .min(2.0); // Maximum risk aversion

    // 3. Calculate Optimal Slice Size (Almgren-Chriss Variation)
    // Formula for urgency factor (k): k = (Gamma * Vol^2) / (2 * Lambda)
    let numerator = effective_gamma * volatility.powi(2);
    let denominator = 2.0 * lambda; 
    
    // Urgency factor is now highly inversely sensitive to Lambda.
    let urgency_factor = if denominator.abs() > 1e-12 {
        (numerator / denominator).sqrt()
    } else {
        // If lambda is near zero (perfect liquidity), set maximum urgency
        2.0 
    };

    let safe_urgency = if urgency_factor.is_nan() || urgency_factor.is_infinite() {
        0.0
    } else {
        urgency_factor
    };

    let raw_slice = total_qty * safe_urgency;

    // Apply Boundary Constraints
    let min_slice = total_qty * 0.0001; // Extremely small slice for highly toxic markets
    let max_slice = total_qty * 0.25;  // Max 25% slice to prevent market abuse 
    let optimal_slice_size = raw_slice.clamp(min_slice, max_slice);

    
    // 4. Calculate Protective Collar (Slippage Tolerance)
    // Formula: Collar = (Vol * sqrt(Lambda)) / sqrt(Gamma)
    // A high Lambda (Impact Risk) should result in a wider, more protective collar.
    let protective_collar = (volatility * lambda.sqrt()) / effective_gamma.sqrt();

    // Ensure the collar is a realistic, small percentage (e.g., max 1% of price movement tolerance)
    let final_collar = protective_collar.max(0.0001).min(0.01); 

    Ok((optimal_slice_size, effective_gamma, final_collar)) 
}


// ==========================================
// MODULE 1: MARKET MICROSTRUCTURE
// ==========================================

/// Calculates Market Quality Metrics: Amihud Illiquidity, Historical Kyle's Lambda, and Imbalance.
/// FIX: Removed the incorrect * 1,000,000.0 scaling on Kyle's Lambda.
#[pyfunction]
fn calculate_market_quality_metrics(
    opens: Vec<f64>,
    closes: Vec<f64>,
    volumes: Vec<f64>,
) -> PyResult<(f64, f64, f64)> {
    let len = opens.len();
    let mut returns_abs = Vec::with_capacity(len);
    let mut dollar_vols = Vec::with_capacity(len);
    let mut signed_vols = Vec::with_capacity(len);
    let mut price_changes = Vec::with_capacity(len); 
    let mut buy_vol = 0.0;
    let mut sell_vol = 0.0;

    for i in 0..len {
        if volumes[i] <= 0.0 || opens[i] <= 0.0 { continue; }

        let ret = (closes[i] - opens[i]) / opens[i];
        let dollar_vol = closes[i] * volumes[i];
        returns_abs.push(ret.abs());
        dollar_vols.push(dollar_vol);

        let sign = if closes[i] >= opens[i] {
            buy_vol += volumes[i];
            1.0
        } else {
            sell_vol += volumes[i];
            // FIX: Removed the semicolon here to make this an expression returning f64
            -1.0 
        };
        signed_vols.push(volumes[i] * sign);
        price_changes.push(closes[i] - opens[i]);
    }

    // 1. Amihud Illiquidity (kept scaling for standard interpretation)
    let amihud_score = if !dollar_vols.is_empty() {
        let sum_ratio: f64 = returns_abs.iter().zip(&dollar_vols).filter(|&(_, v)| *v > 1e-9).map(|(r, v)| r / v).sum();
        let valid_count = dollar_vols.iter().filter(|v| **v > 1e-9).count() as f64;
        if valid_count > 0.0 { (sum_ratio / valid_count) * 1_000_000.0 } else { 0.0 }
    } else { 0.0 };

    // 2. Historical Kyle's Lambda (Linear Regression)
    // CRITICAL FIX: Removed the * 1_000_000.0 scaling. Lambda is now in (Price Change / Volume) units.
    let kyles_lambda = if signed_vols.len() > 1 {
        let n = signed_vols.len() as f64;
        let sum_x: f64 = signed_vols.iter().sum();
        let sum_y: f64 = price_changes.iter().sum();
        let sum_xy: f64 = signed_vols.iter().zip(&price_changes).map(|(x, y)| x * y).sum();
        let sum_xx: f64 = signed_vols.iter().map(|x| x * x).sum();

        let numerator = n * sum_xy - sum_x * sum_y;
        let denominator = n * sum_xx - sum_x * sum_x;

        if denominator.abs() > 1e-9 { numerator / denominator } else { 0.0 }
    } else { 0.0 };

    // 3. Imbalance
    let total_vol = buy_vol + sell_vol;
    let imbalance = if total_vol > 0.0 { (buy_vol - sell_vol) / total_vol } else { 0.0 };

    Ok((amihud_score, kyles_lambda, imbalance))
}

// ==========================================
// MODULE 2: JUMP RISK ESTIMATOR
// ==========================================

/// Detects "Jump Risk" (Fat Tails) in asset returns.
/// Returns: (Normal Volatility, Jump Probability, Jump Intensity Score)
#[pyfunction]
fn calculate_jump_risk(closes: Vec<f64>) -> PyResult<(f64, f64, f64)> {
    if closes.len() < 2 { return Ok((0.0, 0.0, 0.0)); }

    let mut log_returns = Vec::with_capacity(closes.len() - 1);
    for i in 1..closes.len() {
        if closes[i - 1] > 0.0 && closes[i] > 0.0 {
            log_returns.push((closes[i] / closes[i - 1]).ln());
        }
    }

    let n = log_returns.len() as f64;
    if n == 0.0 { return Ok((0.0, 0.0, 0.0)); }

    let mean: f64 = log_returns.iter().sum::<f64>() / n;
    let variance: f64 = log_returns.iter().map(|&r| (r - mean).powi(2)).sum::<f64>() / n;
    let std_dev = variance.sqrt();

    let threshold = 3.0 * std_dev;
    let mut jump_count = 0.0;
    let mut jump_magnitude_sum = 0.0;

    for &r in &log_returns {
        if (r - mean).abs() > threshold {
            jump_count += 1.0;
            jump_magnitude_sum += (r - mean).abs();
        }
    }

    let jump_probability = jump_count / n;
    let jump_intensity = if jump_count > 0.0 { (jump_magnitude_sum / jump_count) / std_dev } else { 0.0 };

    Ok((std_dev, jump_probability, jump_intensity))
}

// ==========================================
// MODULE 3: BASE OPTIMAL EXECUTION (Stub)
// ==========================================
#[pyfunction]
fn calculate_optimal_slice(
    total_qty: f64,
    // FIX: Variables prefixed with '_' to silence 'unused variable' warnings.
    _risk_aversion: f64,
    _volatility: f64,
    _lambda: f64,
) -> PyResult<f64> {
    // Deprecated in favor of calculate_dynamic_execution_params
    Ok(total_qty * 0.1)
}

// ==========================================
// MODULE 4: AUDIT
// ==========================================

#[pyfunction]
fn get_audit_timestamp() -> PyResult<u128> {
    let start = SystemTime::now();
    let since_the_epoch = start
        .duration_since(UNIX_EPOCH)
        .expect("Time went backwards");
    Ok(since_the_epoch.as_nanos())
}


// ==========================================
// MODULE 5: LIQUIDITY SURFACE
// ==========================================

/// Calculates a Liquidity Surface (Heatmap) of Volume distribution over Time and Spread.
#[pyfunction]
fn calculate_liquidity_surface(
    spreads: Vec<f64>,
    volumes: Vec<f64>,
    timestamps: Vec<f64>,
    time_bins: usize,
    spread_bins: usize,
) -> PyResult<(Vec<f64>, (f64, f64), (f64, f64))> {
    let len = spreads.len();
    if len != volumes.len() || len != timestamps.len() || len == 0 {
         return Ok((vec![0.0; time_bins * spread_bins], (0.0, 0.0), (0.0, 0.0)));
    }

    let mut min_time = f64::MAX;
    let mut max_time = f64::MIN;
    let mut min_spread = f64::MAX;
    let mut max_spread = f64::MIN;

    for &t in &timestamps { if t < min_time { min_time = t; } if t > max_time { max_time = t; } }
    for &s in &spreads { if s.is_normal() && s < min_spread { min_spread = s; } if s.is_normal() && s > max_spread { max_spread = s; } }

    if min_time == f64::MAX || min_spread == f64::MAX {
        return Ok((vec![0.0; time_bins * spread_bins], (0.0, 0.0), (0.0, 0.0)));
    }

    if (max_time - min_time).abs() < 1e-9 { max_time += 1.0; }
    if (max_spread - min_spread).abs() < 1e-9 { max_spread += 0.01; }

    let mut grid = vec![0.0; time_bins * spread_bins];
    let time_step = (max_time - min_time) / (time_bins as f64);
    let spread_step = (max_spread - min_spread) / (spread_bins as f64);

    for i in 0..len {
        let t = timestamps[i];
        let s = spreads[i];
        let v = volumes[i];

        if v <= 0.0 || s.is_nan() || t.is_nan() { continue; }

        let mut t_idx = ((t - min_time) / time_step).floor() as usize;
        let mut s_idx = ((s - min_spread) / spread_step).floor() as usize;

        if t_idx >= time_bins { t_idx = time_bins - 1; }
        if s_idx >= spread_bins { s_idx = spread_bins - 1; }

        let idx = t_idx * spread_bins + s_idx;
        if idx < grid.len() { grid[idx] += v; }
    }

    Ok((grid, (min_time, max_time), (min_spread, max_spread)))
}

// ==========================================
// MODULE 6: ASSET-SPECIFIC LAMBDA ENGINE
// ==========================================

/// Calculates Kyle's Lambda with asset-class specific microstructure adjustments
/// using the Square-Root Law of Market Impact.
/// HARDENED: Now applies MAX_SAFE_LAMBDA clamp.
#[pyfunction]
fn calculate_kyle_lambda_asset_specific(
    asset_class: &str,
    order_size: f64,
    volatility: f64,
    market_depth: f64,
) -> PyResult<f64> {
    let config = MarketConfig::get_config(asset_class);

    const C: f64 = 0.0001; 
    const BETA: f64 = 0.5;

    let adapted_vol = volatility * config.vol_multiplier;
    let effective_depth = order_size.min(market_depth) * config.depth_factor;

    // Default to maximum impact if effective depth is zero (toxic)
    if effective_depth <= 1e-9 {
        return Ok(MAX_SAFE_LAMBDA);
    }

    let final_vol = match asset_class.to_uppercase().as_str() {
        "FUTURES" | "COMMODITIES" | "ENERGY" => {
            let tick_adjustment = (config.tick_size / effective_depth).sqrt().min(1.0);
            adapted_vol * (1.0 + tick_adjustment)
        },
        _ => adapted_vol,
    };

    let raw_lambda = C * final_vol / effective_depth.powf(BETA);
    
    // Clamp the final lambda value to prevent catastrophic execution scenarios (like the 8.5)
    Ok(raw_lambda.max(0.0).min(MAX_SAFE_LAMBDA))
}

// ==========================================
// MODULE 7: LOW-LATENCY UDP STREAMER
// ==========================================

/// Streams the Lambda signal over UDP in a fixed-format binary packet.
#[pyfunction]
fn stream_lambda_udp(
    asset_class: &str,
    lambda_value: f64,
    target_ip: &str,
    target_port: u16,
) -> PyResult<String> {
    let asset_id: u8 = match asset_class.to_uppercase().as_str() {
        "EQUITIES" => b'E', "FUTURES" => b'F', "FX" => b'X', "CRYPTO" => b'C', 
        "COMMODITIES" => b'M', "ENERGY" => b'G', "PREDICTION_MARKETS" => b'P',
        _ => b'?',
    };

    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("Time went backwards")
        .as_nanos() as u64;

    let mut packet = Vec::with_capacity(13);
    packet.extend_from_slice(&timestamp.to_be_bytes());
    packet.push(asset_id);
    packet.extend_from_slice(&(lambda_value as f32).to_be_bytes());

    let target_addr = format!("{}:{}", target_ip, target_port);

    match UdpSocket::bind("0.0.0.0:0") {
        Ok(socket) => {
            match socket.send_to(&packet, &target_addr) {
                Ok(bytes_sent) => {
                    Ok(format!(
                        "Sent {} bytes to {} (T={}, Asset={}, Lambda={:.6})",
                        bytes_sent, target_addr, timestamp, asset_id as char, lambda_value
                    ))
                }
                Err(e) => Err(PyErr::new::<pyo3::exceptions::PyIOError, _>(
                    format!("Failed to send UDP packet: {}", e)
                )),
            }
        }
        Err(e) => Err(PyErr::new::<pyo3::exceptions::PyIOError, _>(
            format!("Failed to bind UDP socket: {}", e)
        )),
    }
}

// ==========================================
// MODULE 10: REGIME SWITCHING (SL-HUNT DETECTION)
// ==========================================

/// Uses volatility and market impact (Lambda) to classify the current market regime.
/// The most critical regime is 'SL_HUNT' (Stop-Loss Hunt), which triggers extreme risk aversion.
#[pyfunction]
fn calculate_market_regime(
    volatility: f64,
    kyles_lambda: f64,
    vol_threshold: f64, 
    lambda_threshold: f64,
) -> PyResult<String> {
    // Check for extreme conditions first (SL-Hunt)
    if volatility > vol_threshold * 1.5 && kyles_lambda > lambda_threshold * 1.5 {
        // High Volatility AND High Impact = Toxic Market (Stop-Loss Hunt)
        return Ok("SL_HUNT".to_string());
    }

    // Check for high-risk transition
    if volatility > vol_threshold || kyles_lambda > lambda_threshold {
        // High Volatility OR High Impact = Warning State
        return Ok("TRANSITION".to_string());
    }

    // Default stable regime
    Ok("NORMAL".to_string())
}
// 

// ==========================================
// MODULE 11: OPTIMAL STOPPING (EXIT BOUNDARY)
// ==========================================

/// Calculates the mathematically optimal exit price (stopping boundary)
/// to maximize expected profit based on market drift and decay.
/// This replaces static stop-loss/take-profit targets.
#[pyfunction]
fn calculate_optimal_exit_price(
    entry_price: f64,
    time_remaining: f64, // Time left until position must close (e.g., in seconds)
    volatility: f64,
    drift: f64, // Expected price drift (per time unit)
    alpha_decay_rate: f64, // How quickly the alpha signal is expected to lose edge (e.g., 0.1)
) -> PyResult<(f64, f64)> { // Returns (Optimal Take-Profit Price, Optimal Stop-Loss Price)
    
    if time_remaining <= 0.0 || volatility <= 1e-9 {
        // If time is up or no volatility, assume no movement, use entry price + drift
        return Ok((entry_price + drift * 0.001, entry_price - drift * 0.001));
    }

    // 1. Calculate the urgency/decay factor (kappa)
    // FIX: Alpha DECAYS over time, so we use NEGATIVE exponential
    // kappa → 1 when time_remaining is small (urgent)
    // kappa → 0 when time_remaining is large (less value in waiting)
    let kappa = (-alpha_decay_rate * time_remaining / 60.0).exp(); // Normalize time to minutes
    
    // 2. The critical diffusion term (accounts for volatility)
    // Using 3 sigma as the base boundary (captures 99.7% of moves)
    // The sqrt(time) follows from Brownian motion theory
    let sigma_scaled = volatility * time_remaining.sqrt();
    let diffusion_term = 3.0 * sigma_scaled * entry_price; // Scale by price for absolute values

    // 3. Apply kappa to urgency-adjust the boundaries
    // Lower kappa (longer time) = tighter boundaries (less edge remaining)
    // Higher kappa (shorter time) = wider boundaries (need to capture move now)
    let urgency_factor = 0.5 + (0.5 * kappa); // Range: [0.5, 1.0]
    let adjusted_diffusion = diffusion_term * urgency_factor;

    // 4. Optimal Take-Profit Boundary (Upper Boundary)
    let optimal_take_profit = entry_price + (drift * time_remaining * entry_price) + adjusted_diffusion;

    // 5. Optimal Stop-Loss Boundary (Lower Boundary)
    // Use golden ratio (0.618) for asymmetric stop-loss (tighter than TP)
    let optimal_stop_loss = entry_price + (drift * time_remaining * entry_price) - (adjusted_diffusion * 0.618);

    Ok((optimal_take_profit, optimal_stop_loss))
}
// 


// ==========================================
// PYTHON MODULE DEFINITION
// ==========================================

#[pymodule]
fn pnl_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Core Microstructure & Risk
    m.add_function(wrap_pyfunction!(calculate_market_quality_metrics, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_jump_risk, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_optimal_slice, m)?)?;
    m.add_function(wrap_pyfunction!(get_audit_timestamp, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_liquidity_surface, m)?)?;
    
    // Lambda Engine and Streaming
    m.add_function(wrap_pyfunction!(calculate_kyle_lambda_asset_specific, m)?)?;
    m.add_function(wrap_pyfunction!(stream_lambda_udp, m)?)?;
    
    // HARDENING MODULES (TCM Filter & Collar)
    m.add_function(wrap_pyfunction!(calculate_dynamic_execution_params, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_pre_trade_pnl_filter, m)?)?; 

    // NEW STRATEGY MODULES
    m.add_function(wrap_pyfunction!(calculate_market_regime, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_optimal_exit_price, m)?)?;

    Ok(())
}