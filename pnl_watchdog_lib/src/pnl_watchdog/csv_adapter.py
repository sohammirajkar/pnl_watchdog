"""
CSV Adapter - Parse trade logs from Indian brokers.

Supports:
- Zerodha (Kite) tradebook exports
- Angel One tradebook exports
- Generic OHLCV format for premium/price data
"""

import csv
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger("PnLWatchdog.CSVAdapter")


# ==============================================================================
# ZERODHA FORMAT
# ==============================================================================

def parse_zerodha_tradebook(file_path: str) -> List[Dict[str, Any]]:
    """
    Parse Zerodha Kite tradebook CSV export.
    
    Expected columns:
    - symbol, trade_type, quantity, price, trade_date, trade_time, order_id
    
    Args:
        file_path: Path to CSV file
    
    Returns:
        List of normalized trade dicts
    """
    trades = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        # Zerodha often has a header row
        reader = csv.DictReader(f)
        
        for row in reader:
            try:
                # Normalize column names (Zerodha uses various formats)
                symbol = row.get('symbol', row.get('Symbol', row.get('tradingsymbol', '')))
                trade_type = row.get('trade_type', row.get('Trade Type', row.get('type', '')))
                qty = float(row.get('quantity', row.get('Quantity', row.get('qty', 0))))
                price = float(row.get('price', row.get('Price', row.get('average_price', 0))))
                
                # Parse date/time
                trade_date = row.get('trade_date', row.get('Trade Date', row.get('fill_timestamp', '')))
                trade_time = row.get('trade_time', row.get('Trade Time', ''))
                
                if trade_date and trade_time:
                    dt_str = f"{trade_date} {trade_time}"
                elif trade_date:
                    dt_str = trade_date
                else:
                    dt_str = None
                
                # Try parsing various date formats
                trade_datetime = None
                if dt_str:
                    for fmt in [
                        '%Y-%m-%d %H:%M:%S',
                        '%d-%m-%Y %H:%M:%S',
                        '%Y-%m-%d',
                        '%d-%m-%Y'
                    ]:
                        try:
                            trade_datetime = datetime.strptime(dt_str.strip(), fmt)
                            break
                        except ValueError:
                            continue
                
                trades.append({
                    'symbol': symbol.strip().upper(),
                    'side': 'buy' if 'buy' in trade_type.lower() else 'sell',
                    'qty': qty,
                    'price': price,
                    'trade_time': trade_datetime,
                    'broker': 'zerodha',
                    'order_id': row.get('order_id', row.get('Order ID', '')),
                    'exchange': row.get('exchange', row.get('Exchange', 'NSE'))
                })
                
            except Exception as e:
                logger.warning(f"Skipping row due to parse error: {e}")
                continue
    
    logger.info(f"Parsed {len(trades)} trades from Zerodha export")
    return trades


# ==============================================================================
# ANGEL ONE FORMAT
# ==============================================================================

def parse_angel_tradebook(file_path: str) -> List[Dict[str, Any]]:
    """
    Parse Angel One tradebook CSV export.
    
    Expected columns:
    - Script Name, Buy/Sell, Qty, Price, Trade Date, Trade Time
    """
    trades = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            try:
                symbol = row.get('Script Name', row.get('Symbol', row.get('script', '')))
                side_raw = row.get('Buy/Sell', row.get('Side', row.get('transaction_type', '')))
                qty = float(row.get('Qty', row.get('Quantity', row.get('qty', 0))))
                price = float(row.get('Price', row.get('Trade Price', row.get('price', 0))))
                
                trade_date = row.get('Trade Date', row.get('Date', ''))
                trade_time = row.get('Trade Time', row.get('Time', ''))
                
                dt_str = f"{trade_date} {trade_time}".strip()
                trade_datetime = None
                for fmt in ['%d-%m-%Y %H:%M:%S', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M:%S']:
                    try:
                        trade_datetime = datetime.strptime(dt_str, fmt)
                        break
                    except ValueError:
                        continue
                
                trades.append({
                    'symbol': symbol.strip().upper(),
                    'side': 'buy' if 'buy' in side_raw.lower() or side_raw.upper() == 'B' else 'sell',
                    'qty': qty,
                    'price': price,
                    'trade_time': trade_datetime,
                    'broker': 'angel',
                    'order_id': row.get('Order ID', row.get('order_id', '')),
                    'exchange': row.get('Exchange', 'NSE')
                })
                
            except Exception as e:
                logger.warning(f"Skipping row: {e}")
                continue
    
    logger.info(f"Parsed {len(trades)} trades from Angel One export")
    return trades


# ==============================================================================
# GENERIC OHLCV FORMAT
# ==============================================================================

def parse_generic_ohlcv(file_path: str) -> List[Dict[str, float]]:
    """
    Parse generic OHLCV candle data.
    
    Expected columns: timestamp/date, open, high, low, close, volume
    
    Args:
        file_path: Path to CSV file
    
    Returns:
        List of candle dicts suitable for hunt detection
    """
    candles = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            try:
                # Flexible column naming
                open_price = float(row.get('open', row.get('Open', row.get('o', 0))))
                high_price = float(row.get('high', row.get('High', row.get('h', 0))))
                low_price = float(row.get('low', row.get('Low', row.get('l', 0))))
                close_price = float(row.get('close', row.get('Close', row.get('c', 0))))
                volume = float(row.get('volume', row.get('Volume', row.get('v', 0))))
                
                if open_price > 0 and close_price > 0:
                    candles.append({
                        'open': open_price,
                        'high': high_price,
                        'low': low_price,
                        'close': close_price,
                        'volume': volume
                    })
                    
            except Exception as e:
                logger.warning(f"Skipping candle row: {e}")
                continue
    
    logger.info(f"Parsed {len(candles)} candles from OHLCV file")
    return candles


# ==============================================================================
# AUTO-DETECT FORMAT
# ==============================================================================

def parse_csv_auto(file_path: str) -> Dict[str, Any]:
    """
    Auto-detect CSV format and parse accordingly.
    
    Returns:
        Dict with 'type' (trades/candles) and 'data' list
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        # Read first line to detect format
        first_line = f.readline().lower()
    
    # Detect by column names
    if 'tradingsymbol' in first_line or 'trade_type' in first_line:
        return {'type': 'trades', 'data': parse_zerodha_tradebook(file_path), 'broker': 'zerodha'}
    elif 'script name' in first_line or 'buy/sell' in first_line:
        return {'type': 'trades', 'data': parse_angel_tradebook(file_path), 'broker': 'angel'}
    elif 'open' in first_line and 'close' in first_line and 'volume' in first_line:
        return {'type': 'candles', 'data': parse_generic_ohlcv(file_path), 'broker': None}
    else:
        # Try generic OHLCV as fallback
        try:
            candles = parse_generic_ohlcv(file_path)
            if candles:
                return {'type': 'candles', 'data': candles, 'broker': None}
        except:
            pass
        
        raise ValueError(f"Could not detect CSV format for {file_path}")


# ==============================================================================
# ANALYSIS HELPERS
# ==============================================================================

def analyze_trades_with_hunt_detection(
    trades: List[Dict],
    candle_data: List[Dict],
    asset_class: str = "EQUITIES"
) -> List[Dict]:
    """
    Analyze historical trades and calculate what the hunt score would have been.
    
    Args:
        trades: List of parsed trades
        candle_data: Historical OHLCV data covering the trade period
        asset_class: Asset type for Lambda calculation
    
    Returns:
        List of trades enriched with hunt_score_at_trade field
    """
    try:
        from pnl_watchdog.stoploss_hunt_detector import calculate_hunt_risk_score
    except ImportError:
        logger.error("Hunt detector not available")
        return trades
    
    for trade in trades:
        try:
            # Use candle data up to trade time
            # In production, you'd filter candles by timestamp
            result = calculate_hunt_risk_score(
                candles=candle_data,
                asset_class=asset_class,
                order_size=trade['qty']
            )
            trade['hunt_score_at_trade'] = result.hunt_score
            trade['was_safe'] = result.safe_to_trade
            trade['hunt_verdict'] = result.verdict
            
        except Exception as e:
            logger.warning(f"Could not calculate hunt score for trade: {e}")
            trade['hunt_score_at_trade'] = None
    
    return trades


__all__ = [
    'parse_zerodha_tradebook',
    'parse_angel_tradebook',
    'parse_generic_ohlcv',
    'parse_csv_auto',
    'analyze_trades_with_hunt_detection'
]
