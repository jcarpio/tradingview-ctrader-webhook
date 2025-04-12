# ctrader.py

class CTrader:
    def __init__(self, client_id, client_secret, access_token):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token

    def place_market_order(self, account_id, symbol, direction, volume):
        # Simulación de envío de orden — aquí conectarías con la API real de cTrader
        print(f"[cTrader SDK] Orden: {direction.upper()} {volume} de {symbol} para cuenta {account_id}")
        return {
            "order_id": "fake-order-id-123456",
            "status": "executed",
            "symbol": symbol,
            "direction": direction,
            "volume": volume
        }
