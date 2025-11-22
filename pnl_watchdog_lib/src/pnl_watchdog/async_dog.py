import asyncio
import aiohttp
import logging


class AsyncPnLWatchdog:
    def __init__(self, api_key: str, api_secret: str, paper: bool = True, webhook_url: str = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://paper-api.alpaca.markets" if paper else "https://api.alpaca.markets"
        self.webhook_url = webhook_url
        self.headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret,
            "accept": "application/json"
        }

    async def _send_alert(self, message: str):
        """Sends a Discord/Slack alert without blocking."""
        if not self.webhook_url:
            print(f"🚨 (Log Only) {message}")
            return

        async with aiohttp.ClientSession() as session:
            try:
                await session.post(self.webhook_url, json={"content": message})
            except Exception as e:
                print(f"Failed to send alert: {e}")

    async def verify_execution(self, symbol: str, side: str, qty: float, client_order_id: str = None):
        """
        Polls the broker 3 times over 5 seconds. 
        If the trade is never found, it raises an alarm.
        """
        print(f"🔎 Watchdog started for {side} {qty} {symbol}...")

        async with aiohttp.ClientSession() as session:
            # Try 3 times (Initial check, +2s, +4s)
            for attempt in range(1, 4):
                # Wait before checking (Backoff) to allow broker to process
                await asyncio.sleep(2)

                try:
                    async with session.get(
                        f"{self.base_url}/v2/orders",
                        headers=self.headers,
                        params={"status": "all",
                                "limit": 10, "direction": "desc"}
                    ) as resp:
                        if resp.status != 200:
                            print(f"⚠️ Broker API Error: {resp.status}")
                            continue

                        orders = await resp.json()

                        # Matching Logic
                        for order in orders:
                            # match by ID (Strongest match)
                            if client_order_id and order.get('client_order_id') == client_order_id:
                                print(f"✅ Verified: Trade confirmed via ID.")
                                return True

                            # match by Params (Fuzzy match)
                            if (order['symbol'] == symbol and
                                order['side'] == side and
                                    float(order['qty']) == float(qty)):
                                print(f"✅ Verified: Trade confirmed via Params.")
                                return True

                except Exception as e:
                    print(f"⚠️ Watchdog Connection Error: {e}")

        # If we exit the loop, we never found the trade.
        fail_msg = f"🚨 CRITICAL: Trade for {side} {qty} {symbol} MISSING on Broker Ledger!"
        await self._send_alert(fail_msg)
        return False
