"""
Tests for Stop-Loss Hunt Detector Module
"""

import unittest
import sys
import os
from datetime import datetime, timezone, timedelta

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from pnl_watchdog.stoploss_hunt_detector import (
    calculate_hunt_risk_score,
    pre_trade_check,
    calculate_time_risk_score,
    calculate_lambda_risk_score,
    HUNT_RISK_THRESHOLDS
)


class TestHuntRiskScore(unittest.TestCase):
    """Test stop-loss hunt risk scoring."""
    
    def setUp(self):
        """Create sample candle data."""
        # Normal market conditions
        self.normal_candles = [
            {'open': 100, 'high': 101, 'low': 99.5, 'close': 100.5, 'volume': 10000},
            {'open': 100.5, 'high': 102, 'low': 100, 'close': 101.5, 'volume': 12000},
            {'open': 101.5, 'high': 103, 'low': 101, 'close': 102, 'volume': 11000},
            {'open': 102, 'high': 103.5, 'low': 101.5, 'close': 103, 'volume': 13000},
            {'open': 103, 'high': 104, 'low': 102.5, 'close': 103.5, 'volume': 10500},
        ]
        
        # High volatility / imbalanced conditions
        self.volatile_candles = [
            {'open': 100, 'high': 105, 'low': 95, 'close': 95, 'volume': 50000},
            {'open': 95, 'high': 96, 'low': 90, 'close': 91, 'volume': 80000},
            {'open': 91, 'high': 93, 'low': 88, 'close': 89, 'volume': 100000},
            {'open': 89, 'high': 90, 'low': 85, 'close': 86, 'volume': 120000},
            {'open': 86, 'high': 88, 'low': 82, 'close': 83, 'volume': 150000},
        ]

    def test_normal_conditions_low_risk(self):
        """Normal market conditions should have low hunt score."""
        result = calculate_hunt_risk_score(
            candles=self.normal_candles,
            asset_class="EQUITIES",
            order_size=100
        )
        
        self.assertIsNotNone(result)
        self.assertLess(result.hunt_score, HUNT_RISK_THRESHOLDS['HIGH_RISK'])
        
    def test_volatile_conditions_higher_risk(self):
        """Volatile conditions should have higher hunt score."""
        result = calculate_hunt_risk_score(
            candles=self.volatile_candles,
            asset_class="EQUITIES",
            order_size=100
        )
        
        self.assertIsNotNone(result)
        # Should be higher than normal conditions
        normal_result = calculate_hunt_risk_score(
            candles=self.normal_candles,
            asset_class="EQUITIES",
            order_size=100
        )
        self.assertGreater(result.hunt_score, normal_result.hunt_score)

    def test_score_has_all_components(self):
        """Result should have all component scores."""
        result = calculate_hunt_risk_score(
            candles=self.normal_candles,
            asset_class="EQUITIES"
        )
        
        self.assertIsNotNone(result.lambda_score)
        self.assertIsNotNone(result.imbalance_score)
        self.assertIsNotNone(result.jump_score)
        self.assertIsNotNone(result.time_score)
        
        # Component scores should be 0-25 each
        self.assertGreaterEqual(result.lambda_score, 0)
        self.assertLessEqual(result.lambda_score, 25)
        
    def test_protective_collar_calculated(self):
        """Result should include protective collar."""
        result = calculate_hunt_risk_score(candles=self.normal_candles)
        
        self.assertIsNotNone(result.protective_collar)
        self.assertGreater(result.protective_collar, 0)


class TestTimeRiskScore(unittest.TestCase):
    """Test time-of-day risk calculation."""
    
    def test_normal_hours_low_risk(self):
        """Normal trading hours should have low time risk."""
        # 11:00 AM IST
        normal_time = datetime(2024, 12, 4, 11, 0, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
        score = calculate_time_risk_score(normal_time)
        
        self.assertLess(score, 10)  # Should be low
    
    def test_closing_time_high_risk(self):
        """3:00-3:30 PM IST should have high time risk."""
        # 3:15 PM IST
        close_time = datetime(2024, 12, 4, 15, 15, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
        score = calculate_time_risk_score(close_time)
        
        self.assertGreater(score, 10)  # Should be elevated


class TestPreTradeCheck(unittest.TestCase):
    """Test pre-trade safety check."""
    
    def setUp(self):
        self.normal_candles = [
            {'open': 100, 'high': 101, 'low': 99.5, 'close': 100.5, 'volume': 10000}
            for _ in range(10)
        ]
    
    def test_returns_binary_decision(self):
        """Pre-trade check should return a clear go/no-go."""
        result = pre_trade_check(
            symbol="NIFTY84900CE",
            qty=50,
            expected_price=180,
            candles=self.normal_candles
        )
        
        self.assertIsInstance(result.safe_to_execute, bool)
        self.assertIsNotNone(result.reason)
        self.assertIsNotNone(result.recommended_action)

    def test_high_threshold_allows_trade(self):
        """High acceptable risk threshold should allow most trades."""
        result = pre_trade_check(
            symbol="TEST",
            qty=100,
            expected_price=50,
            candles=self.normal_candles,
            max_acceptable_risk=90  # Very high threshold
        )
        
        self.assertTrue(result.safe_to_execute)


class TestLambdaRiskScore(unittest.TestCase):
    """Test Lambda-based risk scoring."""
    
    def test_zero_lambda_zero_score(self):
        """Zero Lambda should give zero score."""
        self.assertEqual(calculate_lambda_risk_score(0), 0)
    
    def test_low_lambda_low_score(self):
        """Low Lambda should give low score."""
        score = calculate_lambda_risk_score(0.0005)
        self.assertLess(score, 10)
    
    def test_high_lambda_high_score(self):
        """High Lambda should give high score."""
        score = calculate_lambda_risk_score(0.02)
        self.assertGreater(score, 20)


if __name__ == '__main__':
    unittest.main()
