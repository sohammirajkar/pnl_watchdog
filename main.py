import asyncio
import requests
import os
from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session


# --- ADD THIS FUNCTION ---
def send_discord_alert(message: str):
    # REPLACE WITH YOUR ACTUAL DISCORD WEBHOOK URL
    WEBHOOK_URL = "https://discord.com/api/webhooks/1441137346044231817/RfVB0xdLRPngSmIi-FQ87IOTdgOKc5gkvuVM4oO4GcsgJsLrrT2_53k1YH7TZhdb8Xcp"

    data = {
        "content": message,
        "username": "PnL Watchdog"
    }
    try:
        requests.post(WEBHOOK_URL, json=data)
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to send Discord alert: {e}")

# --- UPDATE THE LOGIC INSIDE verify_trade_execution ---
# Scroll down to the 'else' block where we print "🚨 ALERT"
        if found:
            print(f"✅ SUCCESS: Trade confirmed on Broker.")
        else:
            msg = f"🚨 CRITICAL ALERT: Strategy '{signal.strategy_id}' signal for {signal.symbol} is MISSING on Broker!"
            print(msg)
            send_discord_alert(msg)  # <--- CALL THE NEW FUNCTION HERE


# --- DATABASE SETUP (Local SQLite) ---
DATABASE_URL = "sqlite:///./pnl.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class UserStrategy(Base):
    __tablename__ = "user_strategies"
    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(String, unique=True, index=True)
    email = Column(String)
    broker_api_key = Column(String)
    broker_api_secret = Column(String)
    broker_endpoint = Column(
        String, default="https://paper-api.alpaca.markets")


Base.metadata.create_all(bind=engine)

app = FastAPI(title="PnL Watchdog")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- DATA MODELS ---


class TradeSignal(BaseModel):
    strategy_id: str
    symbol: str
    side: str
    qty: float


class StrategyRegistration(BaseModel):
    strategy_id: str
    email: str
    api_key: str
    api_secret: str
    endpoint: str = "https://paper-api.alpaca.markets"

# --- CORE LOGIC ---


async def verify_trade_execution(signal: TradeSignal, api_key: str, api_secret: str, endpoint: str):
    print(
        f"🔎 WATCHDOG: Checking broker for {signal.side} {signal.qty} {signal.symbol}...")
    await asyncio.sleep(3)  # Wait for broker

    headers = {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": api_secret,
        "accept": "application/json"
    }

    try:
        # 1. FETCH ORDERS
        response = requests.get(
            f"{endpoint}/v2/orders",
            headers=headers,
            params={"status": "all", "limit": 5, "direction": "desc"}
        )

        if response.status_code != 200:
            print(f"❌ BROKER ERROR: {response.text}")
            return

        # 2. MATCH ORDERS
        recent_orders = response.json()
        found = False
        for order in recent_orders:
            if (order['symbol'] == signal.symbol and
                order['side'] == signal.side and
                    float(order['qty']) == signal.qty):
                found = True
                break

        if found:
            print(f"✅ SUCCESS: Trade confirmed on Broker.")
        else:
            print(f"🚨 ALERT: Trade MISSING on Broker! Alerting user...")

    except Exception as e:
        print(f"❌ EXCEPTION: {e}")

# --- API ENDPOINTS ---


@app.post("/register")
def register_strategy(data: StrategyRegistration, db: Session = Depends(get_db)):
    # Upsert logic (Update if exists, Insert if new)
    existing = db.query(UserStrategy).filter(
        UserStrategy.strategy_id == data.strategy_id).first()
    if existing:
        existing.broker_api_key = data.api_key
        existing.broker_api_secret = data.api_secret
    else:
        new_strat = UserStrategy(
            strategy_id=data.strategy_id, email=data.email,
            broker_api_key=data.api_key, broker_api_secret=data.api_secret,
            broker_endpoint=data.endpoint
        )
        db.add(new_strat)
    db.commit()
    return {"status": "registered", "id": data.strategy_id}


@app.post("/webhook/verify")
async def receive_webhook(signal: TradeSignal, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    user_strat = db.query(UserStrategy).filter(
        UserStrategy.strategy_id == signal.strategy_id).first()
    if not user_strat:
        raise HTTPException(status_code=404, detail="Strategy ID not found.")

    background_tasks.add_task(verify_trade_execution, signal, user_strat.broker_api_key,
                              user_strat.broker_api_secret, user_strat.broker_endpoint)
    return {"status": "received", "message": "Watchdog is verifying..."}

# --- FRONTEND DASHBOARD (HTML/JS) ---


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>PnL Watchdog Dashboard</title>
        <style>
            body { font-family: 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; display: flex; justify-content: center; padding-top: 50px; }
            .container { width: 400px; background: #1e293b; padding: 30px; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
            h2 { color: #38bdf8; border-bottom: 1px solid #334155; padding-bottom: 10px; }
            input, select { width: 100%; padding: 10px; margin: 8px 0; background: #0f172a; border: 1px solid #334155; color: white; border-radius: 6px; box-sizing: border-box;}
            button { width: 100%; padding: 12px; margin-top: 15px; background: #38bdf8; border: none; color: #0f172a; font-weight: bold; border-radius: 6px; cursor: pointer; transition: 0.2s; }
            button:hover { background: #0ea5e9; }
            .status { margin-top: 15px; font-size: 0.9em; color: #94a3b8; text-align: center;}
            .section { margin-bottom: 40px; }
        </style>
    </head>
    <body>
        <div class="container">
            
            <div class="section">
                <h2>⚙️ 1. Configure Watchdog</h2>
                <input type="text" id="reg_id" placeholder="Strategy Name (e.g., MyBot)" value="MyBot">
                <input type="text" id="reg_key" placeholder="Alpaca API Key (PK...)" >
                <input type="password" id="reg_secret" placeholder="Alpaca Secret Key" >
                <button onclick="register()">Save Keys</button>
                <div id="reg_status" class="status"></div>
            </div>

            <div class="section">
                <h2>🚀 2. Simulate Bot Signal</h2>
                <p style="font-size: 0.8rem; color: #64748b;">Clicking this pretends your bot just traded.</p>
                <select id="sim_symbol">
                    <option value="AAPL">AAPL</option>
                    <option value="TSLA">TSLA</option>
                    <option value="BTC/USD">BTC/USD</option>
                </select>
                <select id="sim_side">
                    <option value="buy">Buy</option>
                    <option value="sell">Sell</option>
                </select>
                <button onclick="simulate()" style="background: #22c55e; color: white;">Trigger Webhook</button>
                <div id="sim_status" class="status"></div>
            </div>

        </div>

        <script>
            async function register() {
                const status = document.getElementById('reg_status');
                status.innerText = "Saving...";
                
                const res = await fetch('/register', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        strategy_id: document.getElementById('reg_id').value,
                        email: "user@test.com",
                        api_key: document.getElementById('reg_key').value,
                        api_secret: document.getElementById('reg_secret').value
                    })
                });
                const data = await res.json();
                if(res.ok) status.innerText = "✅ Keys Saved! Ready to monitor.";
                else status.innerText = "❌ Error: " + data.detail;
            }

            async function simulate() {
                const status = document.getElementById('sim_status');
                status.innerText = "Sending Signal...";
                
                const res = await fetch('/webhook/verify', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        strategy_id: document.getElementById('reg_id').value,
                        symbol: document.getElementById('sim_symbol').value,
                        side: document.getElementById('sim_side').value,
                        qty: 1
                    })
                });
                const data = await res.json();
                status.innerText = "✅ Signal Sent! Check Terminal Logs.";
            }
        </script>
    </body>
    </html>
    """
