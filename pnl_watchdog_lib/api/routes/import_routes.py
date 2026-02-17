"""
Import and analytics routes with tenant-scoped access.
"""

import os
import shutil
import tempfile
from typing import Dict, Optional

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.db_connect import get_db
from ...db.models import TradeHistory, User
from ..auth import get_current_user
from pnl_watchdog.importers import (
    AlpacaAPIImporter,
    BinanceCSVImporter,
    BybitAPIImporter,
    ZerodhaCSVImporter,
)

router = APIRouter()


class AlpacaSyncRequest(BaseModel):
    api_key: str = Field(..., min_length=8)
    api_secret: str = Field(..., min_length=8)
    paper: bool = True


class BybitSyncRequest(BaseModel):
    api_key: str = Field(..., min_length=8)
    api_secret: str = Field(..., min_length=8)
    symbol: Optional[str] = None
    market_type: str = Field(default="swap", pattern="^(swap|spot|future|option)$")
    lookback_days: int = Field(default=7, ge=1, le=90)
    limit: int = Field(default=500, ge=10, le=1000)
    testnet: bool = False


async def _is_duplicate_trade(
    db: AsyncSession,
    user_id,
    broker: str,
    symbol: str,
    side: str,
    qty,
    price,
    timestamp,
    order_id: Optional[str],
) -> bool:
    if order_id:
        stmt = (
            select(TradeHistory.id)
            .where(TradeHistory.user_id == user_id)
            .where(TradeHistory.broker == broker)
            .where(TradeHistory.external_order_id == order_id)
            .limit(1)
        )
    else:
        stmt = (
            select(TradeHistory.id)
            .where(TradeHistory.user_id == user_id)
            .where(TradeHistory.broker == broker)
            .where(TradeHistory.symbol == symbol)
            .where(TradeHistory.side == side)
            .where(TradeHistory.qty == qty)
            .where(TradeHistory.price == price)
            .where(TradeHistory.timestamp == timestamp)
            .limit(1)
        )

    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None


async def _save_imported_trades(
    db: AsyncSession,
    current_user: User,
    broker: str,
    import_source: str,
    trades,
) -> Dict[str, int]:
    saved_count = 0
    duplicates_skipped = 0

    for t in trades:
        duplicate = await _is_duplicate_trade(
            db=db,
            user_id=current_user.id,
            broker=broker,
            symbol=t.symbol,
            side=t.side,
            qty=t.qty,
            price=t.price,
            timestamp=t.timestamp,
            order_id=t.order_id,
        )
        if duplicate:
            duplicates_skipped += 1
            continue

        db_trade = TradeHistory(
            user_id=current_user.id,
            broker=broker,
            symbol=t.symbol,
            side=t.side,
            qty=t.qty,
            price=t.price,
            timestamp=t.timestamp,
            import_source=import_source,
            external_order_id=t.order_id or None,
            raw_data=t.raw_data,
        )
        db.add(db_trade)
        saved_count += 1

    await db.commit()
    return {"saved_count": saved_count, "duplicates_skipped": duplicates_skipped}


@router.post("/import/zerodha", tags=["Import"])
async def import_zerodha_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import trade history from Zerodha tradebook CSV for the authenticated user."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        importer = ZerodhaCSVImporter()
        trades = await importer.parse(tmp_path)
        save_result = await _save_imported_trades(
            db=db,
            current_user=current_user,
            broker="zerodha",
            import_source="csv",
            trades=trades,
        )
        return {
            "status": "success",
            "imported_count": save_result["saved_count"],
            "duplicates_skipped": save_result["duplicates_skipped"],
            "errors": importer.errors,
        }
    finally:
        os.unlink(tmp_path)


@router.post("/import/binance", tags=["Import"])
async def import_binance_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import trade history from Binance CSV for the authenticated user."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        importer = BinanceCSVImporter()
        trades = await importer.parse(tmp_path)
        save_result = await _save_imported_trades(
            db=db,
            current_user=current_user,
            broker="binance",
            import_source="csv",
            trades=trades,
        )
        return {
            "status": "success",
            "imported_count": save_result["saved_count"],
            "duplicates_skipped": save_result["duplicates_skipped"],
            "errors": importer.errors,
        }
    finally:
        os.unlink(tmp_path)


@router.post("/import/alpaca", tags=["Import"])
async def sync_alpaca_history(
    request: AlpacaSyncRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sync trade history from Alpaca API using read-only credentials."""
    base_url = "https://paper-api.alpaca.markets" if request.paper else "https://api.alpaca.markets"
    importer = AlpacaAPIImporter(request.api_key, request.api_secret, base_url)
    trades = await importer.parse()

    save_result = await _save_imported_trades(
        db=db,
        current_user=current_user,
        broker="alpaca",
        import_source="api",
        trades=trades,
    )
    return {
        "status": "success",
        "imported_count": save_result["saved_count"],
        "duplicates_skipped": save_result["duplicates_skipped"],
        "errors": importer.errors,
    }


@router.post("/import/bybit", tags=["Import"])
async def sync_bybit_history(
    request: BybitSyncRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Sync Bybit trade history using read-only API key/secret.
    Suitable for perps market makers who want account-level execution telemetry.
    """
    importer = BybitAPIImporter(
        api_key=request.api_key,
        api_secret=request.api_secret,
        symbol=request.symbol,
        market_type=request.market_type,
        lookback_days=request.lookback_days,
        limit=request.limit,
        testnet=request.testnet,
    )
    trades = await importer.parse()

    save_result = await _save_imported_trades(
        db=db,
        current_user=current_user,
        broker="bybit",
        import_source="api",
        trades=trades,
    )
    return {
        "status": "success",
        "imported_count": save_result["saved_count"],
        "duplicates_skipped": save_result["duplicates_skipped"],
        "errors": importer.errors,
    }


@router.get("/stats/pnl", tags=["Analytics"])
async def get_pnl_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get user-scoped trade activity stats."""
    base_filter = TradeHistory.user_id == current_user.id

    total_result = await db.execute(select(func.count(TradeHistory.id)).where(base_filter))
    total_trades = total_result.scalar() or 0

    recent_result = await db.execute(
        select(TradeHistory)
        .where(base_filter)
        .order_by(desc(TradeHistory.timestamp))
        .limit(10)
    )
    recent_trades = recent_result.scalars().all()

    broker_result = await db.execute(
        select(TradeHistory.broker, func.count(TradeHistory.id))
        .where(base_filter)
        .group_by(TradeHistory.broker)
    )
    broker_breakdown = {broker: count for broker, count in broker_result.all()}

    symbol_count = func.count(TradeHistory.id).label("cnt")
    symbol_result = await db.execute(
        select(TradeHistory.symbol, symbol_count)
        .where(base_filter)
        .group_by(TradeHistory.symbol)
        .order_by(desc(symbol_count))
        .limit(5)
    )
    top_symbols = [{"symbol": symbol, "count": count} for symbol, count in symbol_result.all()]

    return {
        "user_id": str(current_user.id),
        "total_trades": total_trades,
        "broker_breakdown": broker_breakdown,
        "top_symbols": top_symbols,
        "recent_activity": [
            {
                "symbol": t.symbol,
                "side": t.side,
                "qty": float(t.qty),
                "price": float(t.price),
                "timestamp": t.timestamp,
                "broker": t.broker,
            }
            for t in recent_trades
        ],
    }
