import pandas as pd
import io
import time

# --- Setup for Simulation ---
# Lot size is 50 units (5 Sensex lots * 10 units/lot)
UNITS_TRADED = 50
LOT_SIZE = 10
IDEAL_EXIT_TIME = '15:00:00'
DELAYED_EXIT_TIME = '15:00:03'

# Simulated tick data showing a rapid spike and crash
# This simulates the price movement between the signal generation (T+0) and the 
# order execution time (T+3s) due to latency.
data = """
Timestamp,Price
14:59:58,310.00
14:59:59,380.00
15:00:00,455.00
15:00:01,460.00
15:00:02,305.00
15:00:03,302.73
15:00:04,301.00
"""

df = pd.read_csv(io.StringIO(data), index_col='Timestamp')
# Convert index to datetime objects (date is arbitrary, only time matters)
df.index = pd.to_datetime(df.index, format='%H:%M:%S')

def calculate_slippage(log_data):
    """
    Calculates the financial loss incurred due to execution delay (slippage).
    
    Args:
        log_data (pd.DataFrame): DataFrame containing price data and timestamps.
    """
    
    try:
        # We need to find the rows where the time string matches, as the index is a DatetimeIndex
        
        # 1. Get the ideal exit price (when the signal was generated)
        ideal_row = log_data[log_data.index.strftime('%H:%M:%S') == IDEAL_EXIT_TIME]
        ideal_exit_price = ideal_row['Price'].iloc[0]
        
        # 2. Get the actual exit price (when the market order was executed)
        delayed_row = log_data[log_data.index.strftime('%H:%M:%S') == DELAYED_EXIT_TIME]
        delayed_exit_price = delayed_row['Price'].iloc[0]
        
        # Calculate the slippage in points
        slippage_points = ideal_exit_price - delayed_exit_price
        
        # Calculate the total financial loss (Cost)
        total_loss_inr = slippage_points * UNITS_TRADED
        
        print("-" * 50)
        print(f"--- PnL Watchdog Slippage Analysis Report ---")
        print(f"Units Traded: {UNITS_TRADED} (5 Lots)")
        print(f"")
        print(f"1. IDEAL EXECUTION (T+0):")
        print(f"   Timestamp: {IDEAL_EXIT_TIME} | Price: {ideal_exit_price:.2f}")
        
        print(f"\n2. ACTUAL DELAYED EXECUTION (T+3s):")
        print(f"   Timestamp: {DELAYED_EXIT_TIME} | Price: {delayed_exit_price:.2f}")
        
        print(f"\n3. COST ANALYSIS:")
        print(f"   Slippage Incurred (Points/Unit): {slippage_points:.2f}")
        print(f"   Total Loss Due to Latency (INR): {total_loss_inr:,.2f}")
        print("-" * 50)
        
        print(f"\nConclusion: PnL Watchdog would have saved {total_loss_inr:,.2f} INR by enforcing a Protective Limit Order at {ideal_exit_price:.2f} at T+0.")

    except IndexError:
        print(f"Error: One of the target timestamps ({IDEAL_EXIT_TIME} or {DELAYED_EXIT_TIME}) was not found in the simulated data.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    calculate_slippage(df)