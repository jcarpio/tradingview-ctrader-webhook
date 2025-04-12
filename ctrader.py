import asyncio
import json
import websockets
import os
import uuid
from dotenv import load_dotenv
from websockets.exceptions import ConnectionClosedOK

load_dotenv()

# Diccionario de símbolos conocidos con su symbolId en la demo de cTrader
SYMBOLS = {
    "BTCUSD": 6080842,
    "ETHUSD": 6080843,
    "EURUSD": 1,
    "XAUUSD": 2,
    # Puedes añadir más aquí si los necesitas
}

class CTrader:
    def __init__(self):
        self.access_token = os.getenv("CTRADER_ACCESS_TOKEN")
        self.account_id = int(os.getenv("ACCOUNT_ID"))
        self.ws = None

    async def connect(self):
        self.ws = await websockets.connect("wss://demo.ctraderapi.com:5035")
        await self.authenticate()
        await self.authenticate_account()
        await self.subscribe_to_events()

    def _build_message(self, payload_type, payload):
        return {
            "clientMsgId": str(uuid.uuid4()),
            "payloadType": payload_type,
            "payload": payload
        }

    async def authenticate(self):
        msg = self._build_message(
            2100,
            {"accessToken": self.access_token}
        )
        await self.send(msg)
        print("[cTrader SDK] ✅ Autenticado correctamente")

    async def authenticate_account(self):
        msg = self._build_message(
            2102,
            {
                "ctidTraderAccountId": self.account_id,
                "accessToken": self.access_token
            }
        )
        await self.send(msg)
        print(f"[cTrader SDK] ✅ Cuenta autenticada correctamente (ID: {self.account_id})")

    async def subscribe_to_events(self):
        msg = self._build_message(
            2164,
            {
                "ctidTraderAccountId": self.account_id,
                "symbolIds": list(SYMBOLS.values())
            }
        )
        await self.send(msg)
        print("[cTrader SDK] 📡 Suscripción a eventos enviada")

    async def send(self, message):
        await self.ws.send(json.dumps(message))

    async def receive(self):
        response = await self.ws.recv()
        return json.loads(response)

    async def place_market_order(self, symbol, side, volume):
        if symbol not in SYMBOLS:
            raise Exception(f"❌ El símbolo {symbol} no está en la lista local. Añádelo a SYMBOLS.")
        symbol_id = SYMBOLS[symbol]

        order_msg = self._build_message(
            2001,
            {
                "accountId": self.account_id,
                "symbolId": symbol_id,
                "orderType": "MARKET",
                "orderSide": side.upper(),  # BUY o SELL
                "volume": int(volume),
                "timeInForce": "FILL_OR_KILL",
                "comment": "Order from TradingView Webhook"
            }
        )

        await self.send(order_msg)
        print(f"[cTrader SDK] ✅ Orden enviada: {side.upper()} {volume} de {symbol} (symbolId: {symbol_id})")

        try:
            while True:
                response = await asyncio.wait_for(self.receive(), timeout=3)
                print(f"[cTrader SDK] 📩 Respuesta recibida:", response)
                if response.get("payloadType") in [2002, 2004, 2006, 2010, 2016]:
                    break
        except asyncio.TimeoutError:
            print("⚠️ El servidor cerró la conexión sin enviar confirmación de orden.")
        except ConnectionClosedOK:
            print("⚠️ Conexión cerrada después del intento de orden. Verifica el symbolId o volumen.")
        finally:
            await self.ws.close()
            print("[cTrader SDK] 🔌 Conexión cerrada correctamente")

# Ejemplo de uso:
# async def main():
#     bot = CTrader()
#     await bot.connect()
#     await bot.place_market_order("BTCUSD", "BUY", 100000)
#
# asyncio.run(main())
