import pnl_core
import numpy as np

def test_liquidity_surface():
    print("\n--- Testing Liquidity Surface ---")
    
    # Create synthetic data with a known "liquidity hole"
    # 100 data points over time
    n = 100
    
    # Spreads: mostly around 0.1, but spike to 0.5 in the middle (time 40-60)
    spreads = [0.1] * 40 + [0.5] * 20 + [0.1] * 40
    
    # Volumes: mostly around 1000, but drop to 100 in the middle (liquidity hole)
    volumes = [1000.0] * 40 + [100.0] * 20 + [1000.0] * 40
    
    # Timestamps: 0 to 99
    timestamps = [float(i) for i in range(n)]
    
    time_bins = 10
    spread_bins = 5
    
    try:
        grid, time_bounds, spread_bounds = pnl_core.calculate_liquidity_surface(
            spreads, volumes, timestamps, time_bins, spread_bins
        )
        
        print(f"Grid size: {len(grid)} (expected: {time_bins * spread_bins})")
        print(f"Time bounds: {time_bounds}")
        print(f"Spread bounds: {spread_bounds}")
        print(f"\nGrid (reshaped to {time_bins}x{spread_bins}):")
        
        # Reshape and display grid
        for t in range(time_bins):
            row = []
            for s in range(spread_bins):
                idx = t * spread_bins + s
                row.append(f"{grid[idx]:8.1f}")
            print(f"Time bin {t}: " + " ".join(row))
        
        # Find the liquidity hole in time bins 4-5 (should have lower volume)
        # Sum all spread bins for each time range
        volume_bins_0_3 = sum(grid[i * spread_bins + s] for i in range(4) for s in range(spread_bins))
        volume_bins_4_5 = sum(grid[i * spread_bins + s] for i in range(4, 6) for s in range(spread_bins))
        volume_bins_6_9 = sum(grid[i * spread_bins + s] for i in range(6, 10) for s in range(spread_bins))
        
        print(f"\nVolume comparison:")
        print(f"  Bins 0-3 (high volume): {volume_bins_0_3}")
        print(f"  Bins 4-5 (liquidity hole): {volume_bins_4_5}")
        print(f"  Bins 6-9 (high volume): {volume_bins_6_9}")
        print(f"  Ratio 4-5 / 0-3: {volume_bins_4_5 / volume_bins_0_3 if volume_bins_0_3 > 0 else 0:.2f}")
        
        # Assertions
        assert len(grid) == time_bins * spread_bins, "Grid size mismatch"
        assert time_bounds == (0.0, 99.0), "Time bounds incorrect"
        # Bins 4-5 should have much lower volume (10% of bins 0-3)
        assert volume_bins_4_5 < volume_bins_0_3 * 0.15, f"Liquidity hole not detected: {volume_bins_4_5} vs {volume_bins_0_3}"
        assert volume_bins_4_5 < volume_bins_6_9 * 0.15, f"Liquidity hole not detected: {volume_bins_4_5} vs {volume_bins_6_9}"
        
        print("\n✅ Liquidity Surface Test Passed")
        print("   The Rust core correctly identified the liquidity hole in time bins 4-5!")
        
        
        
    except Exception as e:
        print(f"❌ Liquidity Surface Test Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_liquidity_surface()
