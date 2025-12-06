"""
Database Models - SQLAlchemy ORM (Async)
"""

from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, BigInteger, Text, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from .db_connect import Base

class User(Base):
    """
    User account model.
    """
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    api_key = Column(String(64), unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    preferences = Column(JSONB, default={})

    # Relationships
    trades = relationship("TradeHistory", back_populates="user", cascade="all, delete-orphan")
    alerts = relationship("RiskAlert", back_populates="user", cascade="all, delete-orphan")


class TradeHistory(Base):
    """
    Centralized trade log for all execution events.
    """
    __tablename__ = "trade_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    
    # Trade Details
    broker = Column(String(50), nullable=False) # 'alpaca', 'zerodha', 'binance', 'manual'
    symbol = Column(String(50), nullable=False, index=True)
    side = Column(String(10), nullable=False)   # 'buy', 'sell'
    qty = Column(Numeric, nullable=False)
    price = Column(Numeric, nullable=False)
    
    # Timestamps
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Performance Metrics
    pnl = Column(Numeric)                 # Realized PnL (filled after close)
    slippage = Column(Numeric)            # Calculated execution slippage
    
    # Execution Intelligence
    hunt_score = Column(Numeric)          # 0-100 Execution Risk Score
    execution_quality = Column(String(20)) # 'EXCELLENT', 'GOOD', 'POOR'
    
    # Metadata
    import_source = Column(String(20), nullable=False) # 'csv', 'api', 'live'
    external_order_id = Column(String(100))
    raw_data = Column(JSONB)

    # Relationships
    user = relationship("User", back_populates="trades")


class RiskAlert(Base):
    """
    Real-time feed of market anomalies.
    """
    __tablename__ = "risk_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    
    symbol = Column(String(50), nullable=False)
    alert_type = Column(String(50), nullable=False) # 'SL_HUNT', 'HIGH_LAMBDA', 'VOL_SPIKE'
    severity = Column(String(20), nullable=False)   # 'INFO', 'WARNING', 'CRITICAL'
    message = Column(Text)
    
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    acknowledged = Column(Boolean, default=False)

    # Relationships
    user = relationship("User", back_populates="alerts")
