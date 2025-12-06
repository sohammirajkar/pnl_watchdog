"""
Verification Script for PnL Watchdog v0.8.0 Core Features
Tests Dynamic Execution Alpha Model and New Asset Classes.
"""
import sys
import os
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "pnl_watchdog_lib", "src"))

import pnl_core

def test_dynamic_execution():
    print("\n" + "="*70)
    print("TEST 1: Dynamic Execution Alpha Model")
    print("="*70)
    
    total_qty = 10000.0
    volatility = 0.02
    lambda_cost = 0.00005
    base_risk_aversion = 0.5
    
    # Case 1: No Alpha (Neutral)
    # Should behave like standard Almgren-Chriss
    slice_neutral, gamma_neutral = pnl_core.calculate_dynamic_execution_params(
        0.0, total_qty, volatility, lambda_cost, base_risk_aversion, 5.0
    )
    
    # Case 2: High Positive Alpha (Strong Edge)
    # Should decrease effective risk aversion (more urgent) -> Larger Slice
    slice_alpha, gamma_alpha = pnl_core.calculate_dynamic_execution_params(
        0.05, total_qty, volatility, lambda_cost, base_risk_aversion, 5.0
    )
    
    print(f"Base Risk Aversion: {base_risk_aversion}")
    print(f"Neutral Slice: {slice_neutral:.2f} (Gamma: {gamma_neutral:.4f})")
    print(f"Alpha Slice:   {slice_alpha:.2f}   (Gamma: {gamma_alpha:.4f})")
    
    assert slice_alpha > slice_neutral, "High Alpha should increase execution speed"
    assert gamma_alpha < gamma_neutral, "High Alpha should lower effective risk aversion"
    
    print("\n✅ Dynamic Execution Logic PASSED")

def test_asset_classes():
    print("\n" + "="*70)
    print("TEST 2: New Asset Classes (Microstructure)")
    print("="*70)
    
    order_size = 100.0
    vol = 0.01
    depth = 10000.0
    
    # Test Crypto (High Vol Multiplier)
    lambda_crypto = pnl_core.calculate_kyle_lambda_asset_specific(
        "CRYPTO", order_size, vol, depth
    )
    
    # Test Equities (Standard)
    lambda_equity = pnl_core.calculate_kyle_lambda_asset_specific(
        "EQUITIES", order_size, vol, depth
    )
    
    # Test Prediction Markets (Shallow Depth)
    lambda_pred = pnl_core.calculate_kyle_lambda_asset_specific(
        "PREDICTION_MARKETS", order_size, vol, depth
    )
    
    print(f"Lambda (Equity): {lambda_equity:.6f}")
    print(f"Lambda (Crypto): {lambda_crypto:.6f}")
    print(f"Lambda (Pred):   {lambda_pred:.6f}")
    
    assert lambda_crypto > lambda_equity, "Crypto should have higher impact (vol multiplier)"
    assert lambda_pred > lambda_crypto, "Prediction Markets should have highest impact (shallow depth)"
    
    print("\n✅ Asset Class Logic PASSED")

if __name__ == "__main__":
    try:
        test_dynamic_execution()
        test_asset_classes()
        print("\n" + "="*70)
        print("✅ ALL v0.8.0 CORE TESTS PASSED")
        print("="*70)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
