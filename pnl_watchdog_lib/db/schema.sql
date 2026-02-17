-- PnL Watchdog MVP Schema
-- Target: PostgreSQL
-- Created: 2025-12-06

-- 1. USERS & AUTH
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    api_key VARCHAR(64) UNIQUE, -- stores SHA-256 hash of key, never plaintext
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    preferences JSONB DEFAULT '{}'::jsonb
);

-- 2. TRADE HISTORY
-- Centralized log for all execution events
CREATE TABLE IF NOT EXISTS trade_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    
    -- Trade Details
    broker VARCHAR(50) NOT NULL, -- 'alpaca', 'zerodha', 'binance', 'manual'
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL,   -- 'buy', 'sell'
    qty DECIMAL NOT NULL,
    price DECIMAL NOT NULL,
    
    -- Timestamps
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Performance Metrics
    pnl DECIMAL,                 -- Realized PnL (filled after close)
    slippage DECIMAL,            -- Calculated execution slippage
    
    -- Execution Intelligence (The "Watchdog" Value Prop)
    hunt_score DECIMAL,          -- 0-100 Execution Risk Score at moment of trade
    execution_quality VARCHAR(20), -- 'EXCELLENT', 'GOOD', 'POOR'
    
    -- Metadata
    import_source VARCHAR(20) NOT NULL, -- 'csv', 'api', 'live'
    external_order_id VARCHAR(100),
    raw_data JSONB -- Full broker response for debugging
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_trades_user_time ON trade_history(user_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trade_history(symbol);
CREATE UNIQUE INDEX IF NOT EXISTS idx_trades_dedupe_external
ON trade_history(user_id, broker, external_order_id)
WHERE external_order_id IS NOT NULL;

-- 3. RISK ALERTS
-- Real-time feed of market anomalies
CREATE TABLE IF NOT EXISTS risk_alerts (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    
    symbol VARCHAR(50) NOT NULL,
    alert_type VARCHAR(50) NOT NULL, -- 'SL_HUNT', 'HIGH_LAMBDA', 'VOL_SPIKE'
    severity VARCHAR(20) NOT NULL,   -- 'INFO', 'WARNING', 'CRITICAL'
    message TEXT,
    
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    acknowledged BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_alerts_user_time ON risk_alerts(user_id, timestamp DESC);
