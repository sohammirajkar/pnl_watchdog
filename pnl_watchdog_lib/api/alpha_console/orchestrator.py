"""
Alpha Execution Console - Gemini LLM Orchestrator

Handles natural language → structured trade intent conversion
using Gemini's Function Calling capability.
"""

import os
import json
from typing import Optional
from datetime import datetime

# Try to import google.generativeai
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None

from .schemas import (
    TradeIntent,
    AssetClass,
    OptionStrategy,
    TRADE_INTENT_FUNCTION_SCHEMA
)


class GeminiOrchestrator:
    """
    Orchestrates Gemini LLM for trade intent parsing.
    Uses Function Calling to extract structured data from natural language.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Gemini orchestrator.
        
        Args:
            api_key: Gemini API key. If not provided, reads from GEMINI_API_KEY env var.
        """
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model = None
        
        if GEMINI_AVAILABLE and self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
    
    @property
    def is_available(self) -> bool:
        """Check if Gemini is properly configured."""
        return GEMINI_AVAILABLE and self.model is not None
    
    def parse_trade_intent(self, user_input: str) -> TradeIntent:
        """
        Parse natural language trading request into structured TradeIntent.
        
        Examples:
            "5000 share iron condor on NVDA" 
                → TradeIntent(ticker="NVDA", quantity=5000, strategy_name=IRON_CONDOR)
            
            "Buy 100 NIFTY 84900 CE"
                → TradeIntent(ticker="NIFTY", quantity=100, action="BUY", ...)
        
        Args:
            user_input: Natural language trading request
            
        Returns:
            Structured TradeIntent object
        """
        if not self.is_available:
            # Fallback to rule-based parsing
            return self._fallback_parse(user_input)
        
        # Use Gemini Function Calling
        try:
            prompt = f"""
You are a trading assistant. Parse the following trading request into structured data.
Extract the ticker, quantity, strategy type, and action.

User request: "{user_input}"

Respond with a JSON object containing:
- ticker: The stock/ETF symbol (e.g., "NVDA", "SPY", "NIFTY")
- asset_class: One of EQUITIES, OPTIONS, FUTURES, FOREX, CRYPTO
- strategy_name: If it's an options strategy (IRON_CONDOR, BULL_CALL_SPREAD, etc.)
- quantity: Number of shares or contracts
- action: BUY, SELL, ANALYZE, ROLL, or MODIFY
- expected_price: If mentioned

Return ONLY valid JSON, no markdown or explanation.
"""
            
            response = self.model.generate_content(prompt)
            
            # Parse the response
            response_text = response.text.strip()
            
            # Clean up markdown if present
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            
            parsed = json.loads(response_text)
            
            # Convert to TradeIntent
            return TradeIntent(
                ticker=parsed.get("ticker", "UNKNOWN").upper(),
                asset_class=AssetClass(parsed.get("asset_class", "EQUITIES")),
                strategy_name=OptionStrategy(parsed["strategy_name"]) if parsed.get("strategy_name") else None,
                quantity=int(parsed.get("quantity", 1)),
                action=parsed.get("action", "ANALYZE"),
                expected_price=parsed.get("expected_price"),
                raw_input=user_input
            )
            
        except Exception as e:
            print(f"Gemini parsing failed: {e}")
            return self._fallback_parse(user_input)
    
    def _fallback_parse(self, user_input: str) -> TradeIntent:
        """
        Rule-based fallback parser when Gemini is unavailable.
        """
        input_lower = user_input.lower()
        input_upper = user_input.upper()
        
        # Extract ticker - use regex to find any ticker-like pattern
        ticker = "UNKNOWN"
        import re
        
        # Strategy 1: Look for "on TICKER" pattern (most reliable)
        # Match word after "on " - the ticker comes AFTER the word "on"
        on_match = re.search(r'\bon\s+([A-Za-z]{1,6})\b', user_input, re.IGNORECASE)
        if on_match:
            ticker = on_match.group(1).upper()
        else:
            # Strategy 2: Look for standalone uppercase words (2-5 chars, not common words)
            # This catches "XDE Iron Condor" or "analyze IP1"
            common_words = {"BUY", "SELL", "THE", "FOR", "AND", "PUT", "CALL", "IRON", "BULL", "BEAR"}
            words = re.findall(r'\b([A-Z]{2,5})\b', input_upper)
            for word in words:
                if word not in common_words and not any(c.isdigit() for c in word):
                    ticker = word
                    break
        
        # Strategy 3: Fallback to common tickers list (for partial matches)
        if ticker == "UNKNOWN":
            common_tickers = [
                "NVDA", "AAPL", "TSLA", "AMD", "MSFT", "GOOG", "GOOGL", "META", "AMZN", "NFLX",
                "SPY", "QQQ", "IWM", "DIA", "VIX", "XLF", "XLE", "XLK", "GLD", "SLV", "TLT",
                "GME", "AMC", "MSTR", "COIN", "PLTR", "RIVN", "LCID",
                "USO", "XOM", "CVX", "OXY",
                "NIFTY", "BANKNIFTY", "SENSEX", "RELIANCE", "TCS", "INFY", "HDFC",
                "BITO", "GBTC", "JPM", "BAC", "GS", "MS",
            ]
            for t in common_tickers:
                if t in input_upper:
                    ticker = t
                    break
        
        # Extract quantity
        quantity = 100  # default
        qty_match = re.search(r'(\d+)\s*(share|contract|lot|qty|quantity)?', input_lower)
        if qty_match:
            quantity = int(qty_match.group(1))
        
        # Detect strategy
        strategy = None
        if "iron condor" in input_lower:
            strategy = OptionStrategy.IRON_CONDOR
        elif "iron butterfly" in input_lower:
            strategy = OptionStrategy.IRON_BUTTERFLY
        elif "bull call" in input_lower or "call spread" in input_lower:
            strategy = OptionStrategy.BULL_CALL_SPREAD
        elif "bear put" in input_lower or "put spread" in input_lower:
            strategy = OptionStrategy.BEAR_PUT_SPREAD
        elif "straddle" in input_lower:
            strategy = OptionStrategy.STRADDLE
        elif "strangle" in input_lower:
            strategy = OptionStrategy.STRANGLE
        elif "covered call" in input_lower:
            strategy = OptionStrategy.COVERED_CALL
        elif " call" in input_lower and " ce" not in input_lower:
            strategy = OptionStrategy.LONG_CALL
        elif " put" in input_lower and " pe" not in input_lower:
            strategy = OptionStrategy.LONG_PUT
        
        # Detect action
        action = "ANALYZE"
        if "buy" in input_lower:
            action = "BUY"
        elif "sell" in input_lower or "short" in input_lower:
            action = "SELL"
        elif "roll" in input_lower:
            action = "ROLL"
        
        # Detect asset class
        asset_class = AssetClass.EQUITIES
        if "option" in input_lower or " ce" in input_lower or " pe" in input_lower or strategy:
            asset_class = AssetClass.OPTIONS
        elif "future" in input_lower:
            asset_class = AssetClass.FUTURES
        elif "forex" in input_lower or "fx" in input_lower:
            asset_class = AssetClass.FOREX
        
        return TradeIntent(
            ticker=ticker,
            asset_class=asset_class,
            strategy_name=strategy,
            quantity=quantity,
            action=action,
            raw_input=user_input
        )
    
    def generate_spoken_response(self, analysis_result: dict) -> str:
        """
        Generate a natural language summary for TTS output.
        
        Args:
            analysis_result: The complete analysis JSON
            
        Returns:
            Natural language summary string
        """
        if not self.is_available:
            return self._fallback_spoken_response(analysis_result)
        
        try:
            prompt = f"""
Based on this trading analysis, generate a brief spoken summary (2-3 sentences max):

{json.dumps(analysis_result, indent=2)}

Focus on:
1. The strategy and ticker
2. The risk verdict (SAFE, CAUTION, HIGH_RISK, DANGER)
3. Any specific recommendation

Be concise. This will be read aloud by text-to-speech.
"""
            
            response = self.model.generate_content(prompt)
            return response.text.strip()
            
        except Exception as e:
            print(f"TTS generation failed: {e}")
            return self._fallback_spoken_response(analysis_result)
    
    def _fallback_spoken_response(self, result: dict) -> str:
        """Fallback spoken response generator."""
        intent = result.get("intent", {})
        risk = result.get("execution_risk", {})
        
        ticker = intent.get("ticker", "the position")
        verdict = risk.get("risk_verdict", "unknown")
        
        if verdict == "SAFE":
            return f"Your {ticker} trade looks safe to execute. Lambda is low in normal range."
        elif verdict == "CAUTION":
            return f"Caution on {ticker}. There's elevated Lambda. Consider using smaller order slices."
        elif verdict == "HIGH_RISK":
            return f"High risk detected on {ticker}. I recommend delaying execution or reducing size significantly."
        else:
            return f"Danger on {ticker}. Market conditions are unfavorable. Do not execute right now."


# Singleton instance
_orchestrator = None

def get_orchestrator() -> GeminiOrchestrator:
    """Get or create the Gemini orchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = GeminiOrchestrator()
    return _orchestrator


__all__ = ["GeminiOrchestrator", "get_orchestrator"]
