
import os
import asyncio
from ctrader_open_api import APIClient, APIClientFactory
from dotenv import load_dotenv

load_dotenv()

# Mapeo local de símbolos a symbolId conocidos (demo)
SYMBOLS = {
    "BTCUSD": 6080842,
    "ETHUSD": 6080843,
    "EURUSD": 1,
    "XAUUSD": 2,
}

class CTrader:
    def __init__(self):
        self.client_id = os.getenv("CTRADER_CLIENT_ID")
        self.client_secret = os.getenv("CTRADER_CLIENT_SECRET")
        self.account_id = int(os.getenv("ACCOUNT_ID"))
        self.access_token = os.getenv("CTRADER_ACCESS_TOKEN")
        self.refresh_token = os.getenv("CTRADER_REFRESH_TOKEN")
        self.client = None

    async def connect(self):
        print("[cTrader SDK] 🔌 Conectando al servidor TCP...")
        factory = APIClientFactory()
        self.client: APIClient = factory.build()
        await self.client.connect()
        await self.client.authenticate(self.client_id, self.client_secret, self.access_token, self.refresh_token)
        print("[cTrader SDK] ✅ Autenticado correctamente")
        await self.client.get_trading_account(self.account_id)
        print(f"[cTrader SDK] ✅ Cuenta autenticada correctamente (ID: {self.account_id})")

    async def place_market_order(self, symbol, side, volume):
        if symbol not in SYMBOLS:
            raise Exception(f"❌ El símbolo {symbol} no está en la lista local. Añádelo a SYMBOLS.")
        symbol_id = SYMBOLS[symbol]
        side_enum = "BUY" if side.upper() == "BUY" else "SELL"

        print(f"[cTrader SDK] 🚀 Enviando orden {side_enum} {volume} de {symbol} (symbolId: {symbol_id})")

        order = await self.client.send_market_order(
            account_id=self.account_id,
            symbol_id=symbol_id,
            order_side=side_enum,
            volume=int(volume),
            comment="Order from TradingView Webhook"
        )

        if order and order.execution_id:
            print(f"[cTrader SDK] ✅ Orden ejecutada con ID: {order.execution_id}")
        else:
            print("⚠️ No se recibió confirmación de ejecución.")

        await self.client.close()
        print("[cTrader SDK] 🔌 Conexión cerrada correctamente")
