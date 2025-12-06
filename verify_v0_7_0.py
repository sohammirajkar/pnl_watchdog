"""
Verification Script for PnL Watchdog v0.7.0 Core Features
Tests Jump Diffusion Estimator and Optimal Execution Slicer.
"""
import sys
import os
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "pnl_watchdog_lib", "src"))

import pnl_core

def test_jump_diffusion():
    print("\n" + "="*70)
    print("TEST 1: Jump Diffusion Estimator")
    print("="*70)

    # Case 1: Normal Distribution (No Jumps)
    np.random.seed(42)
    normal_returns = np.random.normal(0, 0.01, 1000)
    closes_normal = 100 * np.exp(np.cumsum(normal_returns))
    
    vol, prob, intensity = pnl_core.calculate_jump_risk(closes_normal.tolist())
    
    print(f"\nScenario: Normal Market (Gaussian)")
    print(f"  Volatility: {vol:.4f} (Expected ~0.01)")
    print(f"  Jump Prob:  {prob:.2%} (Expected < 1%)")
    print(f"  Intensity:  {intensity:.2f}")
    
    assert prob < 0.05, "Normal market should have low jump probability"

    # Case 2: Market Crash (Jumps)
    crash_returns = normal_returns.copy()
    # Add 5 massive drops (5-10 sigma)
    crash_indices = np.random.choice(1000, 5, replace=False)
    crash_returns[crash_indices] = -0.10  # -10% drops
    
    closes_crash = 100 * np.exp(np.cumsum(crash_returns))
    
    vol_c, prob_c, intensity_c = pnl_core.calculate_jump_risk(closes_crash.tolist())
    
    print(f"\nScenario: Market Crash (Fat Tails)")
    print(f"  Volatility: {vol_c:.4f}")
    print(f"  Jump Prob:  {prob_c:.2%} (Expected > 0%)")
    print(f"  Intensity:  {intensity_c:.2f} (Expected High)")
    
    assert prob_c > 0.0, "Crash market should detect jumps"
    assert intensity_c > 1.0, "Crash jumps should be intense"
    
    print("\n✅ Jump Diffusion Test PASSED")

def test_optimal_slice():
    print("\n" + "="*70)
    print("TEST 2: Almgren-Chriss Optimal Slicer")
    print("="*70)
    
    total_qty = 10000.0
    volatility = 0.02
    lambda_cost = 0.00005 # Price impact per share
    
    # Case 1: Low Urgency (Risk Neutral)
    slice_low = pnl_core.calculate_optimal_slice(total_qty, 0.01, volatility, lambda_cost)
    
    # Case 2: High Urgency (Risk Averse)
    slice_high = pnl_core.calculate_optimal_slice(total_qty, 1.0, volatility, lambda_cost)
    
    print(f"\nTotal Order: {total_qty}")
    print(f"Volatility: {volatility}")
    print(f"Impact Cost: {lambda_cost}")
    
    print(f"\nSlice Size (Low Urgency):  {slice_low:.2f}")
    print(f"Slice Size (High Urgency): {slice_high:.2f}")
    
    assert slice_high > slice_low, "Higher urgency should result in larger initial slices"
    assert slice_low >= total_qty * 0.01, "Slice should respect minimum boundary"
    assert slice_high <= total_qty * 0.50, "Slice should respect maximum boundary"
    
    print("\n✅ Optimal Slicer Test PASSED")

if __name__ == "__main__":
    try:
        test_jump_diffusion()
        test_optimal_slice()
        print("\n" + "="*70)
        print("✅ ALL v0.7.0 CORE TESTS PASSED")
        print("="*70)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
