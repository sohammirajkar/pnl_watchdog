from sqlalchemy import Column, Integer, String, Float, DateTime
from database import Base
from datetime import datetime


class TradeLogDB(Base):
    __tablename__ = "trade_logs"

    id = Column(Integer, primary_key=True, index=True)

    # Segmentation
    user_id = Column(String, index=True)  # <--- NEW FIELD ADDED

    # Trade Details
    symbol = Column(String, index=True)
    side = Column(String)
    qty = Column(Float)
    broker = Column(String)

    # Metrics
    latency_ms = Column(Integer)
    slippage = Column(Float)
    status = Column(String)

    # Metadata
    timestamp = Column(DateTime, default=datetime.utcnow)


# 2. The "Global Map" Table (Anonymous Telemetry)
# This powers the public status page


class TelemetryDB(Base):
    __tablename__ = "global_telemetry"

    id = Column(Integer, primary_key=True, index=True)
    broker = Column(String, index=True)  # e.g. "binance", "alpaca"
    latency_ms = Column(Integer)        # e.g. 45
    status = Column(String)             # "verified" or "anomaly"
    timestamp = Column(DateTime, default=datetime.utcnow)
