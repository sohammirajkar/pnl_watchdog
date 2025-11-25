from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import SessionLocal, engine, Base
from models import TradeLogDB, TelemetryDB
from datetime import datetime, timedelta
from typing import List, Dict

# Initialize Database
Base.metadata.create_all(bind=engine)

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DEPENDENCIES ---


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def verify_key(x_pro_key: str = Header(None)):
    if not x_pro_key or not x_pro_key.startswith("sk_"):
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return x_pro_key.split('_')[-1]

# --- DATA MODELS ---


class TradeLog(BaseModel):
    symbol: str
    side: str
    qty: float
    broker: str
    latency_ms: int
    slippage: float
    status: str


class TelemetryPayload(BaseModel):
    broker: str
    latency_ms: int
    status: str

# --- ENDPOINTS ---


@app.get("/")
async def root():
    return {"status": "online", "service": "PnL Global Oracle"}

# 1. THE PUBLIC "WAZE" ENDPOINT (Anonymous)


@app.post("/v1/telemetry")
async def submit_telemetry(payload: TelemetryPayload, db: Session = Depends(get_db)):
    """
    Free users send data here. No API Key required.
    We only store Broker + Latency. No symbol, no side, no user info.
    """
    new_ping = TelemetryDB(
        broker=payload.broker.lower(),
        latency_ms=payload.latency_ms,
        status=payload.status
    )
    db.add(new_ping)
    db.commit()
    return {"status": "contributed"}

# 2. THE GLOBAL MAP (Aggregated Stats)


@app.get("/v1/global_status")
async def get_global_map(db: Session = Depends(get_db)):
    """
    Returns the 'Traffic Light' status for every broker based on 
    data from the last 5 minutes.
    """
    five_mins_ago = datetime.utcnow() - timedelta(minutes=5)

    # SQL: SELECT broker, AVG(latency_ms), COUNT(*) FROM telemetry WHERE time > 5m GROUP BY broker
    stats = db.query(
        TelemetryDB.broker,
        func.avg(TelemetryDB.latency_ms).label("avg_lat"),
        func.count(TelemetryDB.id).label("volume")
    ).filter(
        TelemetryDB.timestamp >= five_mins_ago
    ).group_by(TelemetryDB.broker).all()

    global_map = {}
    for broker, avg_lat, volume in stats:
        # Determine Status Color
        health = "green"
        if avg_lat > 500:
            health = "red"
        elif avg_lat > 150:
            health = "yellow"

        global_map[broker] = {
            "status": health,
            "latency_ms": int(avg_lat),
            "reports_last_5m": volume
        }

    return global_map

# 3. THE PRO ENDPOINTS (Private)


@app.get("/v1/logs")
async def get_logs(user_id: str = Depends(verify_key), limit: int = 50, db: Session = Depends(get_db)):
    return db.query(TradeLogDB).filter(TradeLogDB.user_id == user_id).order_by(TradeLogDB.timestamp.desc()).limit(limit).all()


@app.post("/v1/log_trade")
async def log_trade(log: TradeLog, user_id: str = Depends(verify_key), db: Session = Depends(get_db)):
    new_log = TradeLogDB(user_id=user_id, **log.dict())
    db.add(new_log)
    db.commit()
    db.refresh(new_log)
    return {"success": True, "log_id": new_log.id}
