use pyo3::prelude::*;
use std::f64::consts::E;
use std::time::{SystemTime, UNIX_EPOCH};

// ==========================================
// MODULE 1: MARKET MICROSTRUCTURE (Existing)
// ==========================================

/// Calculates Market Quality Metrics: Amihud Illiquidity and Kyle's Lambda.
#[pyfunction]
fn calculate_market_quality_metrics(
    opens: Vec<f64>,
    closes: Vec<f64>,
    volumes: Vec<f64>,
) -> PyResult<(f64, f64, f64)> {
    let len = opens.len();
    let mut returns_abs = Vec::with_capacity(len);
    let mut dollar_vols = Vec::with_capacity(len);

    // Vectors for Linear Regression (Kyle's Lambda)
    let mut signed_vols = Vec::with_capacity(len); // X
    let mut price_changes = Vec::with_capacity(len); // Y

    let mut buy_vol = 0.0;
    let mut sell_vol = 0.0;

    for i in 0..len {
        if volumes[i] <= 0.0 || opens[i] <= 0.0 {
            continue;
        }

        // Amihud Logic (Simple Return)
        let ret = (closes[i] - opens[i]) / opens[i];
        let dollar_vol = closes[i] * volumes[i];

        returns_abs.push(ret.abs());
        dollar_vols.push(dollar_vol);

        // Kyle's Lambda Logic
        let sign = if closes[i] >= opens[i] {
            buy_vol += volumes[i];
            1.0
        } else {
            sell_vol += volumes[i];
            -1.0
        };

        signed_vols.push(volumes[i] * sign);
        price_changes.push(closes[i] - opens[i]);
    }

    // 1. Calculate Amihud
    let amihud_score = if !dollar_vols.is_empty() {
        let sum_ratio: f64 = returns_abs
            .iter()
            .zip(&dollar_vols)
            .filter(|&(_, v)| *v > 1e-9)
            .map(|(r, v)| r / v)
            .sum();

        let valid_count = dollar_vols.iter().filter(|v| **v > 1e-9).count() as f64;

        if valid_count > 0.0 {
            (sum_ratio / valid_count) * 1_000_000.0
        } else {
            0.0
        }
    } else {
        0.0
    };

    // 2. Calculate Kyle's Lambda
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

    // 3. Imbalance
    let total_vol = buy_vol + sell_vol;
    let imbalance = if total_vol > 0.0 {
        (buy_vol - sell_vol) / total_vol
    } else {
        0.0
    };

    Ok((amihud_score, kyles_lambda, imbalance))
}

// ==========================================
// MODULE 2: JUMP RISK ESTIMATOR (New)
// ==========================================

/// Detects "Jump Risk" (Fat Tails) in asset returns.
/// Essential for Crypto and Energy markets where distributions are non-Gaussian.
///
/// Returns: (Normal Volatility, Jump Probability, Jump Intensity Score)
#[pyfunction]
fn calculate_jump_risk(closes: Vec<f64>) -> PyResult<(f64, f64, f64)> {
    if closes.len() < 2 {
        return Ok((0.0, 0.0, 0.0));
    }

    // 1. Calculate Log Returns
    let mut log_returns = Vec::with_capacity(closes.len() - 1);
    for i in 1..closes.len() {
        if closes[i - 1] > 0.0 && closes[i] > 0.0 {
            log_returns.push((closes[i] / closes[i - 1]).ln());
        }
    }

    let n = log_returns.len() as f64;
    if n == 0.0 {
        return Ok((0.0, 0.0, 0.0));
    }

    // 2. Calculate Mean and Std Dev (Realized Volatility)
    let mean: f64 = log_returns.iter().sum::<f64>() / n;
    let variance: f64 = log_returns.iter().map(|&r| (r - mean).powi(2)).sum::<f64>() / n;
    let std_dev = variance.sqrt();

    // 3. Detect Jumps (Returns > 3 Sigma)
    // This is a simplified Threshold technique (Bipower Variation proxy)
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

    // Jump Intensity: How violent are the jumps relative to normal vol?
    let jump_intensity = if jump_count > 0.0 {
        (jump_magnitude_sum / jump_count) / std_dev
    } else {
        0.0
    };

    Ok((std_dev, jump_probability, jump_intensity))
}

// ==========================================
// MODULE 3: OPTIMAL EXECUTION (New)
// ==========================================

/// Calculates the Optimal Slice Size using Almgren-Chriss logic.
/// Solves the trade-off between Market Impact (Lambda) and Volatility Risk.
///
/// Inputs:
/// - total_qty: Total shares/contracts to trade
/// - risk_aversion: User parameter (0.1 = Neutral, 1.0 = High Urgency)
/// - volatility: Current asset volatility (from calculate_jump_risk)
/// - lambda: Current Price Impact cost (from calculate_market_quality_metrics)
///
/// Returns: Recommended immediate slice size.
#[pyfunction]
fn calculate_optimal_slice(
    total_qty: f64,
    risk_aversion: f64,
    volatility: f64,
    lambda: f64,
) -> PyResult<f64> {
    // Safety guards
    if total_qty <= 0.0 {
        return Ok(0.0);
    }
    if lambda <= 1e-9 {
        // If no impact cost measured, recommend large slice (or 20% of total)
        return Ok(total_qty * 0.20);
    }

    // Almgren-Chriss simplified "Urgency" formula for single-period lookahead:
    // Optimal Velocity v* ~ sqrt( (Risk * Vol^2) / Lambda )
    // We treat 'risk_aversion' as 'gamma' in the AC model.

    let vol_sq = volatility.powi(2);

    // Calculate the Trading Rate (shares per unit time)
    // Formula: v = sqrt( (gamma * sigma^2) / (2 * eta) ) * Total_X
    // Here eta = lambda.
    let urgency_factor = ((risk_aversion * vol_sq) / (2.0 * lambda)).sqrt();

    // Clamp the urgency to avoid infinity/NaN
    let safe_urgency = if urgency_factor.is_nan() {
        0.0
    } else {
        urgency_factor
    };

    // Assuming we re-evaluate every '1' time unit, the slice is:
    // We apply a sigmoid-like smoothing to prevent recommending > 100% of order
    // Or simply: Slice = Total * Urgency

    let raw_slice = total_qty * safe_urgency;

    // Boundary logic:
    // 1. Never recommend < 1% of order (minimum viable slice)
    // 2. Never recommend > 50% of order in one clip (unless risk aversion is huge)

    let min_slice = total_qty * 0.01;
    let max_slice = total_qty * 0.50;

    let final_slice = raw_slice.clamp(min_slice, max_slice);

    Ok(final_slice)
}

// ==========================================
// MODULE 4: AUDIT (Existing)
// ==========================================

#[pyfunction]
fn get_audit_timestamp() -> PyResult<u128> {
    let start = SystemTime::now();
    let since_the_epoch = start
        .duration_since(UNIX_EPOCH)
        .expect("Time went backwards");
    Ok(since_the_epoch.as_nanos())
}

#[pymodule]
fn pnl_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(calculate_market_quality_metrics, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_jump_risk, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_optimal_slice, m)?)?;
    m.add_function(wrap_pyfunction!(get_audit_timestamp, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_liquidity_surface, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_kyle_lambda_asset_specific, m)?)?;
    m.add_function(wrap_pyfunction!(stream_lambda_udp, m)?)?;
    Ok(())
}

// ==========================================
// MODULE 5: LIQUIDITY SURFACE (New)
// ==========================================

/// Calculates a Liquidity Surface (Heatmap) of Volume distribution over Time and Spread.
///
/// Inputs:
/// - spreads: Vector of bid-ask spreads (or high-low range proxies)
/// - volumes: Vector of trading volumes
/// - timestamps: Vector of timestamps (e.g., seconds from epoch or relative time)
/// - time_bins: Number of bins for the time axis
/// - spread_bins: Number of bins for the spread axis
///
/// Returns: (grid, time_bounds, spread_bounds)
/// - grid: Flattened vector of size time_bins * spread_bins containing accumulated volume
/// - time_bounds: (min_time, max_time)
/// - spread_bounds: (min_spread, max_spread)
#[pyfunction]
fn calculate_liquidity_surface(
    spreads: Vec<f64>,
    volumes: Vec<f64>,
    timestamps: Vec<f64>,
    time_bins: usize,
    spread_bins: usize,
) -> PyResult<(Vec<f64>, (f64, f64), (f64, f64))> {
    let len = spreads.len();
    if len != volumes.len() || len != timestamps.len() {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Input vectors must have the same length",
        ));
    }
    if len == 0 {
         return Ok((vec![], (0.0, 0.0), (0.0, 0.0)));
    }

    // 1. Find Bounds
    let mut min_time = f64::MAX;
    let mut max_time = f64::MIN;
    let mut min_spread = f64::MAX;
    let mut max_spread = f64::MIN;

    for &t in &timestamps {
        if t < min_time { min_time = t; }
        if t > max_time { max_time = t; }
    }
    for &s in &spreads {
        if s < min_spread { min_spread = s; }
        if s > max_spread { max_spread = s; }
    }
    
    // Avoid division by zero if all values are same
    if (max_time - min_time).abs() < 1e-9 { max_time += 1.0; }
    if (max_spread - min_spread).abs() < 1e-9 { max_spread += 0.01; }

    // 2. Initialize Grid (Row-major: Time is rows, Spread is cols)
    // Index = t_idx * spread_bins + s_idx
    let mut grid = vec![0.0; time_bins * spread_bins];

    // 3. Binning
    let time_step = (max_time - min_time) / (time_bins as f64);
    let spread_step = (max_spread - min_spread) / (spread_bins as f64);

    for i in 0..len {
        let t = timestamps[i];
        let s = spreads[i];
        let v = volumes[i];

        let mut t_idx = ((t - min_time) / time_step).floor() as usize;
        let mut s_idx = ((s - min_spread) / spread_step).floor() as usize;

        // Clamp indices to be within bounds (handle max value case)
        if t_idx >= time_bins { t_idx = time_bins - 1; }
        if s_idx >= spread_bins { s_idx = spread_bins - 1; }

        let idx = t_idx * spread_bins + s_idx;
        grid[idx] += v;
    }

    Ok((grid, (min_time, max_time), (min_spread, max_spread)))
}

// ==========================================
// MODULE 6: PHASE 2 - ASSET-SPECIFIC LAMBDA ENGINE
// ==========================================

/// Market configuration for different asset classes
struct MarketConfig {
    tick_size: f64,
    vol_multiplier: f64,
    depth_factor: f64,
}

impl MarketConfig {
    fn get_config(asset_class: &str) -> Self {
        match asset_class.to_uppercase().as_str() {
            "EQUITIES" => MarketConfig {
                tick_size: 0.01,
                vol_multiplier: 1.0,
                depth_factor: 1.0,
            },
            "FUTURES" => MarketConfig {
                tick_size: 0.25,
                vol_multiplier: 0.8,
                depth_factor: 1.5,
            },
            "FX" => MarketConfig {
                tick_size: 0.00005,
                vol_multiplier: 1.5,
                depth_factor: 0.5,
            },
            _ => MarketConfig {
                tick_size: 0.01,
                vol_multiplier: 1.0,
                depth_factor: 1.0,
            },
        }
    }
}

/// Calculates Kyle's Lambda with asset-class specific microstructure adjustments.
/// 
/// Formula: λ(t, s) = C * σ(t) / s^β
/// where:
/// - C = liquidity cost constant
/// - σ(t) = adapted volatility for asset class
/// - s = effective market depth
/// - β = market impact exponent (typically 0.5 - square root law)
///
/// Returns: Lambda value (price impact per unit volume)
#[pyfunction]
fn calculate_kyle_lambda_asset_specific(
    asset_class: &str,
    order_size: f64,
    volatility: f64,
    market_depth: f64,
) -> PyResult<f64> {
    let config = MarketConfig::get_config(asset_class);
    
    // Constants
    const C: f64 = 0.0001; // Liquidity cost constant
    const BETA: f64 = 0.5;  // Market impact exponent (square root law)
    
    // 1. Adapt volatility based on asset class
    let adapted_vol = volatility * config.vol_multiplier;
    
    // 2. Calculate effective depth
    let effective_depth = order_size.min(market_depth) * config.depth_factor;
    
    if effective_depth <= 0.0 {
        // Emergency: Zero depth means infinite impact
        return Ok(999.0);
    }
    
    // 3. Piecewise continuity kernel for futures (tick size effect)
    let final_vol = if asset_class.to_uppercase() == "FUTURES" {
        // Futures have discrete ticks - non-linear impact at boundaries
        let tick_adjustment = (config.tick_size / effective_depth).sqrt();
        adapted_vol * (1.0 + tick_adjustment)
    } else {
        adapted_vol
    };
    
    // 4. Calculate Lambda: C * σ(t) / s^β
    let lambda = C * final_vol / effective_depth.powf(BETA);
    
    Ok(lambda)
}

// ==========================================
// MODULE 7: PHASE 2 - LOW-LATENCY UDP STREAMER
// ==========================================

use std::net::UdpSocket;

/// Streams the Lambda signal over UDP in a fixed-format binary packet.
/// 
/// Packet format (13 bytes):
/// - 8 bytes: Timestamp (u64 nanoseconds)
/// - 1 byte: Asset ID ('E', 'F', 'X')
/// - 4 bytes: Lambda value (f32)
///
/// This enables sub-100ms latency for HFT execution systems.
#[pyfunction]
fn stream_lambda_udp(
    asset_class: &str,
    lambda_value: f64,
    target_ip: &str,
    target_port: u16,
) -> PyResult<String> {
    // 1. Get asset ID
    let asset_id: u8 = match asset_class.to_uppercase().as_str() {
        "EQUITIES" => b'E',
        "FUTURES" => b'F',
        "FX" => b'X',
        _ => b'?',
    };
    
    // 2. Get high-resolution timestamp (nanoseconds)
    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("Time went backwards")
        .as_nanos() as u64;
    
    // 3. Build the packet (13 bytes total)
    let mut packet = Vec::with_capacity(13);
    packet.extend_from_slice(&timestamp.to_be_bytes());  // 8 bytes
    packet.push(asset_id);                                // 1 byte
    packet.extend_from_slice(&(lambda_value as f32).to_be_bytes()); // 4 bytes
    
    // 4. Send UDP packet
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
