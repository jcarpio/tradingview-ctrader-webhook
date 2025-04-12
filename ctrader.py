import requests
import os

class CTrader:
    def __init__(self, client_id, client_secret, access_token):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.base_url = "https://api.spotware.com"  # endpoint real

    def place_market_order(self, account_id, symbol, order_type, volume):
        url = f"{self.base_url}/connect/trading/accounts/{account_id}/orders/market"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "symbol": symbol,
            "volume": volume,
            "side": order_type.lower(),  # "buy" o "sell"
            "type": "market",
            "comment": "TradingView webhook order"
        }

        response = requests.post(url, json=payload, headers=headers)

        if response.status_code == 200:
            data = response.json()
            print("[cTrader SDK] ✅ Orden ejecutada:", data)
            return {"order_id": data.get("orderId", "unknown")}
        else:
            print("[cTrader SDK] ❌ Error al ejecutar orden:", response.status_code, response.text)
            raise Exception(f"API Error: {response.status_code} - {response.text}")
