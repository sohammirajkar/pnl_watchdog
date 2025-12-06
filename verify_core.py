import pnl_core
import math
import time

def test_market_quality_metrics():
    print("\n--- Testing Market Quality Metrics ---")
    # Sample data: Price changes correlated with volume (Linear relationship)
    # Vol: 100 -> dP: 1, Vol: 200 -> dP: 2, etc.
    opens = [100.0, 100.0, 100.0, 100.0, 100.0]
    closes = [101.0, 102.0, 103.0, 104.0, 105.0]
    volumes = [100.0, 200.0, 300.0, 400.0, 500.0]
    
    try:
        amihud, lambda_val, imbalance = pnl_core.calculate_market_quality_metrics(opens, closes, volumes)
        print(f"Amihud: {amihud}")
        print(f"Kyle's Lambda: {lambda_val}")
        print(f"Imbalance: {imbalance}")
        
        # Basic assertions
        assert amihud >= 0, "Amihud should be non-negative"
        assert lambda_val > 0, "Lambda should be positive for price impact"
        assert imbalance > 0, "Imbalance should be positive (buying pressure)"
        print("✅ Market Quality Metrics Test Passed")
    except Exception as e:
        print(f"❌ Market Quality Metrics Test Failed: {e}")

def test_jump_risk():
    print("\n--- Testing Jump Risk Estimator ---")
    # Sample data with a jump
    closes = [100.0] * 50 + [120.0] + [100.0] * 49
    
    try:
        vol, jump_prob, intensity = pnl_core.calculate_jump_risk(closes)
        print(f"Volatility: {vol}")
        print(f"Jump Probability: {jump_prob}")
        print(f"Jump Intensity: {intensity}")
        
        assert vol >= 0, "Volatility should be non-negative"
        assert 0 <= jump_prob <= 1, "Jump probability should be between 0 and 1"
        print("✅ Jump Risk Test Passed")
    except Exception as e:
        print(f"❌ Jump Risk Test Failed: {e}")

def test_optimal_slice():
    print("\n--- Testing Optimal Slice ---")
    total_qty = 10000.0
    risk_aversion = 0.5
    volatility = 0.02
    lambda_val = 0.05
    
    try:
        slice_size = pnl_core.calculate_optimal_slice(total_qty, risk_aversion, volatility, lambda_val)
        print(f"Total Qty: {total_qty}")
        print(f"Optimal Slice: {slice_size}")
        
        assert slice_size > 0, "Slice size should be positive"
        assert slice_size <= total_qty, "Slice size should not exceed total quantity"
        print("✅ Optimal Slice Test Passed")
    except Exception as e:
        print(f"❌ Optimal Slice Test Failed: {e}")

def test_audit_timestamp():
    print("\n--- Testing Audit Timestamp ---")
    try:
        ts = pnl_core.get_audit_timestamp()
        print(f"Timestamp (ns): {ts}")
        assert ts > 0, "Timestamp should be positive"
        print("✅ Audit Timestamp Test Passed")
    except Exception as e:
        print(f"❌ Audit Timestamp Test Failed: {e}")

if __name__ == "__main__":
    test_market_quality_metrics()
    test_jump_risk()
    test_optimal_slice()
    test_audit_timestamp()
