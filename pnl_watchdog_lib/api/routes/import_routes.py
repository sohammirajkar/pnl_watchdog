"""
Import & Stats Routes
"""

import shutil
import os
import tempfile
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from pnl_watchdog.importers import ZerodhaCSVImporter, BinanceCSVImporter, AlpacaAPIImporter
from pnl_watchdog.db.models import TradeHistory, User
from pnl_watchdog.db.db_connect import get_db

router = APIRouter()

# ------------------------------------------------------------------------------
# IMPORT ENDPOINTS
# ------------------------------------------------------------------------------

@router.post("/import/zerodha", tags=["Import"])
async def import_zerodha_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Import trade history from Zerodha tradebook CSV."""
    
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        importer = ZerodhaCSVImporter()
        trades = await importer.parse(tmp_path)
        
        saved_count = 0
        user_id = None 
        # TODO: Get actual user_id from auth dependency. 
        # For MVP, we might need a default user or create one on the fly.
        
        for t in trades:
            # Simple deduplication check could go here
            
            db_trade = TradeHistory(
                user_id=user_id, # Nullable for now or fixed UUID
                broker="zerodha",
                symbol=t.symbol,
                side=t.side,
                qty=t.qty,
                price=t.price,
                timestamp=t.timestamp,
                import_source="csv",
                external_order_id=t.order_id,
                raw_data=t.raw_data
            )
            db.add(db_trade)
            saved_count += 1
            
        await db.commit()
        
        return {
            "status": "success", 
            "imported_count": saved_count,
            "errors": importer.errors
        }
        
    finally:
        os.unlink(tmp_path)
        

@router.post("/import/binance", tags=["Import"])
async def import_binance_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Import trade history from Binance Trade History CSV."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        importer = BinanceCSVImporter()
        trades = await importer.parse(tmp_path)
        
        saved_count = 0
        for t in trades:
            db_trade = TradeHistory(
                broker="binance",
                symbol=t.symbol,
                side=t.side,
                qty=t.qty,
                price=t.price,
                timestamp=t.timestamp,
                import_source="csv",
                raw_data=t.raw_data
            )
            db.add(db_trade)
            saved_count += 1
            
        await db.commit()
        
        return {
            "status": "success",
            "imported_count": saved_count,
            "errors": importer.errors
        }
    finally:
        os.unlink(tmp_path)


@router.post("/import/alpaca", tags=["Import"])
async def sync_alpaca_history(
    api_key: str,
    api_secret: str,
    paper: bool = True,
    db: AsyncSession = Depends(get_db)
):
    """Sync trade history from Alpaca API."""
    base_url = "https://paper-api.alpaca.markets" if paper else "https://api.alpaca.markets"
    importer = AlpacaAPIImporter(api_key, api_secret, base_url)
    
    trades = await importer.parse()
    
    saved_count = 0
    for t in trades:
        # Check if exists (basic check by order_id)
        # Real impl would do a DB lookup here
        
        db_trade = TradeHistory(
            broker="alpaca",
            symbol=t.symbol,
            side=t.side,
            qty=t.qty,
            price=t.price,
            timestamp=t.timestamp,
            import_source="api",
            external_order_id=t.order_id,
            raw_data=t.raw_data
        )
        db.add(db_trade)
        saved_count += 1
        
    await db.commit()
    
    return {
        "status": "success",
        "imported_count": saved_count,
        "errors": importer.errors
    }


# ------------------------------------------------------------------------------
# STATS ENDPOINTS
# ------------------------------------------------------------------------------

@router.get("/stats/pnl", tags=["Analytics"])
async def get_pnl_stats(db: AsyncSession = Depends(get_db)):
    """Get aggregated PnL statistics."""
    
    # Total Trades
    result = await db.execute(select(func.count(TradeHistory.id)))
    total_trades = result.scalar() or 0
    
    # Recent trades
    result = await db.execute(
        select(TradeHistory)
        .order_by(desc(TradeHistory.timestamp))
        .limit(10)
    )
    recent_trades = result.scalars().all()
    
    return {
        "total_trades": total_trades,
        "recent_activity": [
            {
                "symbol": t.symbol,
                "side": t.side,
                "qty": float(t.qty),
                "price": float(t.price),
                "timestamp": t.timestamp,
                "broker": t.broker
            }
            for t in recent_trades
        ]
    }
