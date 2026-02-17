"""
PnL Watchdog Cloud API - FastAPI Backend

REST API for stop-loss hunt detection and pre-trade safety checks.
Deploy with: uvicorn api.main:app --host 0.0.0.0 --port 8000
"""

import sys
import os
from datetime import datetime, timezone
from typing import Optional
import uuid

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from .models import (
    HuntScoreRequest, HuntScoreResponse,
    PreTradeCheckRequest, PreTradeCheckResponse,
    ExecutionPassportRequest, ExecutionPassportResponse,
    HealthResponse, ComponentScores, RawMetrics, Recommendations, HuntRiskSummary
)
from .auth import (
    RegisterRequest,
    RegisterResponse,
    create_or_rotate_api_key,
    get_current_user,
)
from ..db.db_connect import get_db, init_db
from ..db.models import User

# Import core functions
try:
    from pnl_watchdog.stoploss_hunt_detector import (
        calculate_hunt_risk_score,
        pre_trade_check,
        HUNT_RISK_THRESHOLDS
    )
    HUNT_DETECTOR_AVAILABLE = True
except ImportError as e:
    HUNT_DETECTOR_AVAILABLE = False
    print(f"Warning: Hunt detector not available: {e}")

# Check Rust core
try:
    import pnl_core
    RUST_CORE_AVAILABLE = True
except ImportError:
    RUST_CORE_AVAILABLE = False


# ==============================================================================
# APP CONFIGURATION
# ==============================================================================

app = FastAPI(
    title="PnL Watchdog API",
    description="Stop-Loss Hunt Detection & Pre-Trade Safety Checks for Quant Traders",
    version="0.10.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Include Alpha Console router
try:
    from .alpha_console import alpha_router
    app.include_router(alpha_router)
    ALPHA_CONSOLE_AVAILABLE = True
except ImportError as e:
    ALPHA_CONSOLE_AVAILABLE = False
    print(f"Warning: Alpha Console not available: {e}")

# Include Import Router (New MVP Feature)
try:
    from .routes.import_routes import router as import_router
    app.include_router(import_router)
    print("✅ Import Router loaded")
except ImportError as e:
    print(f"❌ Import Router failed to load: {e}")


# CORS for web clients
allowed_origins = [
    origin.strip()
    for origin in os.environ.get(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:5173",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# SIMPLE API KEY AUTH (for rate limiting)
# ==============================================================================

# In production, use a proper auth system
VALID_API_KEYS = {
    "demo-key-for-testing",
    "pnl-watchdog-free-tier"
}

async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """Simple API key verification. Returns None for free tier (rate limited)."""
    if x_api_key and x_api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid X-API-Key.")
    return x_api_key


# ==============================================================================
# ENDPOINTS
# ==============================================================================

from fastapi.responses import HTMLResponse

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Check API health and component availability."""
    return HealthResponse(
        status="healthy",
        version="0.9.0",
        rust_core_available=RUST_CORE_AVAILABLE,
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@app.post("/v1/auth/register", response_model=RegisterResponse, tags=["Auth"])
async def register_api_user(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a user email and return an API key.
    If the email already exists, key is rotated and returned once.
    """
    user, plain_key = await create_or_rotate_api_key(db, request.email)
    return RegisterResponse(
        user_id=str(user.id),
        email=user.email,
        api_key=plain_key,
    )


@app.get("/v1/auth/me", tags=["Auth"])
async def whoami(current_user: User = Depends(get_current_user)):
    """Validate API key and return the authenticated user."""
    return {
        "user_id": str(current_user.id),
        "email": current_user.email,
        "created_at": current_user.created_at,
    }

@app.get("/", response_class=HTMLResponse, tags=["Frontend"])
async def serve_landing():
    """Serve the Info-Landing Page."""
    landing_path = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'landing.html')
    with open(landing_path, 'r', encoding='utf-8') as f:
        return f.read()

@app.get("/app", response_class=HTMLResponse, tags=["Frontend"])
async def serve_app():
    """Serve the Dashboard App."""
    app_path = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'app.html')
    with open(app_path, 'r', encoding='utf-8') as f:
        return f.read()



@app.post("/v1/hunt-score", response_model=HuntScoreResponse, tags=["Risk Analysis"])
async def get_hunt_score(
    request: HuntScoreRequest,
    api_key: Optional[str] = Depends(verify_api_key)
):
    """
    Calculate stop-loss hunt risk score.
    
    Returns a 0-100 score indicating the likelihood of a stop-loss hunt.
    Higher scores mean more danger.
    
    **Thresholds:**
    - < 30: SAFE - Normal market conditions
    - 30-50: CAUTION - Proceed with smaller slices
    - 50-70: HIGH RISK - Consider delaying
    - > 70: DANGER - Do NOT execute
    """
    if not HUNT_DETECTOR_AVAILABLE:
        raise HTTPException(status_code=503, detail="Hunt detector not available")
    
    # Convert Pydantic models to dicts
    candles = [c.model_dump() for c in request.candles]
    
    result = calculate_hunt_risk_score(
        candles=candles,
        asset_class=request.asset_class,
        order_size=request.order_size,
        market_depth=request.market_depth
    )
    
    return HuntScoreResponse(
        symbol=request.symbol,
        hunt_score=result.hunt_score,
        safe_to_trade=result.safe_to_trade,
        verdict=result.verdict,
        components=ComponentScores(
            lambda_risk=result.lambda_score,
            imbalance_risk=result.imbalance_score,
            jump_risk=result.jump_score,
            time_risk=result.time_score
        ),
        metrics=RawMetrics(
            kyles_lambda=result.lambda_value,
            volume_imbalance=result.volume_imbalance,
            jump_probability=result.jump_probability
        ),
        recommendations=Recommendations(
            protective_collar=result.protective_collar,
            recommended_slice_pct=result.recommended_slice_pct,
            delay_seconds=result.delay_seconds
        )
    )


@app.post("/v1/pre-check", response_model=PreTradeCheckResponse, tags=["Risk Analysis"])
async def pre_trade_safety_check(
    request: PreTradeCheckRequest,
    api_key: Optional[str] = Depends(verify_api_key)
):
    """
    Pre-trade safety check.
    
    Call this BEFORE every trade to get a go/no-go decision.
    Returns whether it's safe to execute and recommended actions.
    
    **Critical for Indian F&O:** 
    Time-based risk is automatically increased during 3:00-3:30 PM IST.
    """
    if not HUNT_DETECTOR_AVAILABLE:
        raise HTTPException(status_code=503, detail="Hunt detector not available")
    
    candles = [c.model_dump() for c in request.candles]
    
    result = pre_trade_check(
        symbol=request.symbol,
        qty=request.qty,
        expected_price=request.expected_price,
        candles=candles,
        asset_class=request.asset_class,
        market_depth=request.market_depth,
        max_acceptable_risk=request.max_acceptable_risk
    )
    
    return PreTradeCheckResponse(
        safe_to_execute=result.safe_to_execute,
        reason=result.reason,
        recommended_action=result.recommended_action,
        hunt_risk=HuntRiskSummary(
            score=result.hunt_risk.hunt_score,
            verdict=result.hunt_risk.verdict,
            protective_collar=result.hunt_risk.protective_collar,
            recommended_slice_pct=result.hunt_risk.recommended_slice_pct
        )
    )


@app.post("/v1/execution-passport", response_model=ExecutionPassportResponse, tags=["Audit"])
async def generate_execution_passport(
    request: ExecutionPassportRequest,
    api_key: Optional[str] = Depends(verify_api_key)
):
    """
    Generate an Execution Passport.
    
    Creates a forensic audit record with risk metrics at the time of order submission.
    Store these passports for compliance and post-trade analysis.
    """
    if not HUNT_DETECTOR_AVAILABLE:
        raise HTTPException(status_code=503, detail="Hunt detector not available")
    
    candles = [c.model_dump() for c in request.candles]
    
    # Calculate risk at time of execution
    hunt_result = calculate_hunt_risk_score(
        candles=candles,
        asset_class="EQUITIES",
        order_size=request.qty,
        market_depth=1_000_000.0
    )
    
    # Generate passport
    passport_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    
    # Get nanosecond timestamp if Rust is available
    if RUST_CORE_AVAILABLE:
        try:
            timestamp_ns = pnl_core.get_audit_timestamp()
        except:
            timestamp_ns = int(now.timestamp() * 1_000_000_000)
    else:
        timestamp_ns = int(now.timestamp() * 1_000_000_000)
    
    return ExecutionPassportResponse(
        passport_id=passport_id,
        symbol=request.symbol,
        side=request.side,
        qty=request.qty,
        expected_price=request.expected_price,
        timestamp_ns=timestamp_ns,
        hunt_score=hunt_result.hunt_score,
        safe_to_trade=hunt_result.safe_to_trade,
        protective_collar=hunt_result.protective_collar,
        verdict=hunt_result.verdict,
        created_at=now.isoformat()
    )


@app.get("/v1/thresholds", tags=["Configuration"])
async def get_risk_thresholds():
    """Get the current hunt risk thresholds."""
    if not HUNT_DETECTOR_AVAILABLE:
        return {
            "SAFE": 30,
            "CAUTION": 50,
            "HIGH_RISK": 70,
            "DANGER": 85
        }
    return HUNT_RISK_THRESHOLDS


# ==============================================================================
# STARTUP
# ==============================================================================

@app.on_event("startup")
async def startup_event():
    print("🐶 PnL Watchdog API v0.9.0 starting...")
    print(f"   Rust Core: {'✅' if RUST_CORE_AVAILABLE else '❌'}")
    print(f"   Hunt Detector: {'✅' if HUNT_DETECTOR_AVAILABLE else '❌'}")
    if os.environ.get("AUTO_INIT_DB", "true").lower() == "true":
        await init_db()
        print("   DB Init: ✅")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
