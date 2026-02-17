import requests
import os

# 1. Set DISCORD_WEBHOOK_URL in your environment before running
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")


def test_discord():
    if not WEBHOOK_URL:
        print("❌ DISCORD_WEBHOOK_URL is not set.")
        return

    print(f"Attempting to send to: {WEBHOOK_URL[:30]}...")

    data = {
        "content": "🚨 This is a TEST bark from the Watchdog!",
        "username": "PnL Watchdog"
    }

    try:
        response = requests.post(WEBHOOK_URL, json=data)

        # This line forces Python to tell us if the status code is bad (400/404/500)
        print(f"Status Code: {response.status_code}")
        print(f"Response Body: {response.text}")

        if response.status_code == 204:
            print("✅ SUCCESS! Check your Discord channel now.")
        else:
            print("❌ FAILURE: Discord rejected the message.")

    except Exception as e:
        print(f"❌ CONNECTION ERROR: {e}")


if __name__ == "__main__":
    test_discord()
